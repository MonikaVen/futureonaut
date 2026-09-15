from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path


SEED_DIR = Path(__file__).resolve().parents[1] / "seed_games"
SDK_PATH = Path(__file__).resolve().parents[1] / "sdk" / "learnplay-sdk.js"


class SeedProgressHookTests(unittest.TestCase):
    def test_sdk_exposes_stage_helper(self) -> None:
        source = SDK_PATH.read_text(encoding="utf-8")
        self.assertIn("stage: function", source)
        self.assertIn("sessionClosed", source)

    def test_every_seed_game_emits_progress(self) -> None:
        missing = []
        for html in sorted(SEED_DIR.glob("*.html")):
            text = html.read_text(encoding="utf-8", errors="replace")
            if "LearnPlay.stage" not in text and "LearnPlay.progress" not in text:
                missing.append(html.name)
        self.assertEqual(missing, [], f"games missing LearnPlay progress hooks: {missing}")

    def test_manifest_games_all_have_hooks(self) -> None:
        manifest = json.loads((SEED_DIR / "manifest.json").read_text(encoding="utf-8"))
        missing = []
        for item in manifest:
            path = SEED_DIR / item["file"]
            text = path.read_text(encoding="utf-8", errors="replace")
            if "LearnPlay.stage" not in text and "LearnPlay.progress" not in text:
                missing.append(item["file"])
        self.assertEqual(missing, [])

    def test_templates_emit_progress(self) -> None:
        root = Path(__file__).resolve().parents[1] / "templates"
        missing = []
        for html in sorted(root.glob("*/index.html")):
            text = html.read_text(encoding="utf-8")
            if "LearnPlay.stage" not in text and "LearnPlay.progress" not in text:
                missing.append(str(html.relative_to(root)))
        self.assertEqual(missing, [])

    def test_sdk_stage_emits_level_then_complete(self) -> None:
        script = f"""
const fs = require('fs');
const vm = require('vm');
const events = [];
const sandbox = {{
  Date,
  CustomEvent: class CustomEvent {{
    constructor(type, init) {{ this.type = type; this.detail = init && init.detail; }}
  }}
}};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
sandbox.parent = {{ postMessage(msg) {{ events.push(msg); }} }};
vm.runInNewContext(fs.readFileSync({json.dumps(str(SDK_PATH))}, 'utf8'), sandbox);
sandbox.LearnPlay.stage(2, 5, {{ label: 'Neuron', points: 10 }});
sandbox.LearnPlay.stage(5, 5, {{ complete: true, label: 'Done' }});
sandbox.LearnPlay.complete({{ score: 99 }});
console.log(JSON.stringify(events.map(e => ({{ type: e.type, payload: e.payload }}))));
"""
        result = subprocess.run(
            ["node", "-e", script],
            check=True,
            capture_output=True,
            text=True,
        )
        events = json.loads(result.stdout)
        types = [e["type"] for e in events]
        self.assertIn("level_complete", types)
        self.assertIn("milestone", types)
        self.assertIn("score", types)
        self.assertIn("complete", types)
        self.assertEqual(types.count("complete"), 1)
        complete = next(e for e in events if e["type"] == "complete")
        self.assertEqual(complete["payload"]["levelsCompleted"], 5)
        self.assertEqual(complete["payload"]["totalLevels"], 5)


if __name__ == "__main__":
    unittest.main()
