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
        self.assertIn("answer", types)
        self.assertIn("complete", types)
        self.assertEqual(types.count("complete"), 1)
        complete = next(e for e in events if e["type"] == "complete")
        self.assertEqual(complete["payload"]["levelsCompleted"], 5)
        self.assertEqual(complete["payload"]["totalLevels"], 5)

    def test_sdk_fit_emits_resize(self) -> None:
        script = f"""
const fs = require('fs');
const vm = require('vm');
const events = [];
const doc = {{
  readyState: 'complete',
  documentElement: {{ scrollHeight: 2400, offsetHeight: 800 }},
  body: {{ scrollHeight: 2380, offsetHeight: 780 }},
  addEventListener() {{}},
}};
const sandbox = {{
  Date,
  document: doc,
  addEventListener() {{}},
  CustomEvent: class CustomEvent {{
    constructor(type, init) {{ this.type = type; this.detail = init && init.detail; }}
  }}
}};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
sandbox.parent = {{ postMessage(msg) {{ events.push(msg); }} }};
vm.runInNewContext(fs.readFileSync({json.dumps(str(SDK_PATH))}, 'utf8'), sandbox);
sandbox.LearnPlay.fit();
console.log(JSON.stringify(events.filter(e => e.type === 'resize').map(e => e.payload)));
"""
        result = subprocess.run(
            ["node", "-e", script],
            check=True,
            capture_output=True,
            text=True,
        )
        payloads = json.loads(result.stdout)
        self.assertGreaterEqual(len(payloads), 1)
        self.assertEqual(payloads[0]["height"], 2400)

    def test_i18n_pack_covers_ui_languages(self) -> None:
        path = SDK_PATH.parent / "learnplay-i18n.js"
        self.assertTrue(path.is_file())
        text = path.read_text(encoding="utf-8")
        self.assertIn("LEARNPLAY_I18N", text)
        for code in ("en", "lt", "lv", "et", "fi", "sv", "no"):
            self.assertIn(f'"{code}"', text)
        self.assertIn("Reset", text)

    def test_inject_sdk_includes_i18n_before_sdk(self) -> None:
        from app.services.storage import inject_sdk_into_html

        html = "<html><head><title>G</title></head><body></body></html>"
        out = inject_sdk_into_html(html)
        self.assertIn("LEARNPLAY_I18N", out)
        self.assertIn('source: "learnplay-sdk"', out)
        self.assertNotIn('src="./learnplay-sdk.js"', out)
        self.assertLess(out.index("LEARNPLAY_I18N"), out.index('source: "learnplay-sdk"'))

        already = inject_sdk_into_html('<head><script src="./learnplay-sdk.js"></script></head>')
        self.assertIn("LEARNPLAY_I18N", already)
        self.assertIn('source: "learnplay-sdk"', already)
        self.assertNotIn('src="./learnplay-sdk.js"', already)
        self.assertEqual(already.count('source: "learnplay-sdk"'), 1)
        again = inject_sdk_into_html(already)
        self.assertEqual(again.count('source: "learnplay-sdk"'), 1)

    def test_sdk_translates_and_applies_prefs(self) -> None:
        i18n_path = SDK_PATH.parent / "learnplay-i18n.js"
        script = f"""
const fs = require('fs');
const vm = require('vm');
const events = [];
const attrs = {{}};
const styleNode = {{ id: '', textContent: '' }};
const html = {{
  style: {{}},
  lang: 'en',
  setAttribute(k, v) {{ attrs[k] = v; }},
  getAttribute(k) {{ return attrs[k]; }},
  appendChild() {{}},
}};
const nodes = {{}};
const doc = {{
  readyState: 'loading',
  documentElement: html,
  body: null,
  head: {{ appendChild(el) {{ if (el && el.id) nodes[el.id] = el; }} }},
  getElementById(id) {{ return nodes[id] || null; }},
  createElement() {{ return styleNode; }},
  addEventListener() {{}},
}};
const sandbox = {{
  Date,
  document: doc,
  addEventListener() {{}},
  CustomEvent: class CustomEvent {{
    constructor(type, init) {{ this.type = type; this.detail = init && init.detail; }}
  }}
}};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
sandbox.parent = {{ postMessage(msg) {{ events.push(msg); }} }};
vm.runInNewContext(
  fs.readFileSync({json.dumps(str(i18n_path))}, 'utf8') + '\\n' +
  fs.readFileSync({json.dumps(str(SDK_PATH))}, 'utf8'),
  sandbox
);
sandbox.LearnPlay.setPrefs({{ theme: 'dark', lang: 'lt' }});
const afterLt = {{
  theme: attrs['data-lp-theme'],
  lang: attrs['data-lp-lang'],
  htmlLang: html.lang,
  resetLt: sandbox.LearnPlay.t('Reset')
}};
sandbox.LearnPlay.setPrefs({{ lang: 'fi' }});
const resetFiFromLt = sandbox.LearnPlay.t('Atstatyti');
const resetFiDirect = sandbox.LearnPlay.t('Reset');
console.log(JSON.stringify(Object.assign(afterLt, {{
  resetFiFromLt,
  resetFiDirect,
  hasSetPrefs: typeof sandbox.LearnPlay.setPrefs === 'function',
  hasT: typeof sandbox.LearnPlay.t === 'function'
}})));
"""
        result = subprocess.run(
            ["node", "-e", script],
            check=True,
            capture_output=True,
            text=True,
        )
        data = json.loads(result.stdout)
        self.assertTrue(data["hasSetPrefs"])
        self.assertTrue(data["hasT"])
        self.assertEqual(data["theme"], "dark")
        self.assertEqual(data["lang"], "lt")
        self.assertEqual(data["htmlLang"], "lt")
        self.assertEqual(data["resetLt"], "Atstatyti")
        self.assertEqual(data["resetFiFromLt"], "Nollaa")
        self.assertEqual(data["resetFiDirect"], "Nollaa")

    def test_templates_use_learnplay_t(self) -> None:
        root = Path(__file__).resolve().parents[1] / "templates"
        missing = []
        for html in sorted(root.glob("*/index.html")):
            text = html.read_text(encoding="utf-8")
            if "LearnPlay.t" not in text:
                missing.append(str(html.relative_to(root)))
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
