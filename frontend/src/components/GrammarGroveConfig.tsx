import { useState } from "react";
import {
  GROVE_LEVELS,
  parseGrammarGroveConfig,
  serializeGrammarGroveConfig,
  type GroveConfig,
} from "../grammarGrove";

type LevelDraft = { correct: string; wrong: string };

function wordsToText(words: string[]): string {
  return words.join("\n");
}

function textToWords(value: string): string[] {
  return value
    .split(/\n|,/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function GrammarGroveConfigEditor({
  value,
  onChange,
}: {
  value: string;
  onChange: (next: string) => void;
}) {
  const config = parseGrammarGroveConfig(value);
  const [levelIndex, setLevelIndex] = useState(0);
  const [drafts, setDrafts] = useState<Record<number, LevelDraft>>({});
  const level = Math.min(levelIndex, config.levels.length - 1);
  const meta = GROVE_LEVELS[level];
  const correctText = drafts[level]?.correct ?? wordsToText(config.levels[level].correct);
  const wrongText = drafts[level]?.wrong ?? wordsToText(config.levels[level].wrong);

  function commit(next: GroveConfig) {
    onChange(serializeGrammarGroveConfig(next));
  }

  function updateLevel(kind: "correct" | "wrong", text: string) {
    setDrafts((prev) => ({
      ...prev,
      [level]: {
        correct: kind === "correct" ? text : (prev[level]?.correct ?? wordsToText(config.levels[level].correct)),
        wrong: kind === "wrong" ? text : (prev[level]?.wrong ?? wordsToText(config.levels[level].wrong)),
      },
    }));
    const levels = config.levels.map((item, index) =>
      index === level ? { ...item, [kind]: textToWords(text) } : item,
    );
    commit({ ...config, levels });
  }

  return (
    <div className="grove-config">
      <p className="meta">
        Set the words for all eight levels. Teacher view opens the forest with these lists. Published students play the same words.
      </p>
      <label>
        Lesson name
        <input
          value={config.lessonName}
          maxLength={70}
          onChange={(e) => commit({ ...config, lessonName: e.target.value })}
        />
      </label>
      <label className="row" style={{ gap: 8, alignItems: "center" }}>
        <input
          type="checkbox"
          checked={config.requireTrash}
          onChange={(e) => commit({ ...config, requireTrash: e.target.checked })}
        />
        Require wrong words in the trash before the portal opens
      </label>
      <div className="grove-nav">
        <button
          className="btn secondary btn-sm"
          type="button"
          disabled={level === 0}
          onClick={() => setLevelIndex(level - 1)}
        >
          ←
        </button>
        <div>
          <strong>{meta.name}</strong>
          <span className="meta">
            {level + 1} / {GROVE_LEVELS.length} · up to {meta.correctMax} correct · {meta.wrongMax} incorrect
          </span>
        </div>
        <button
          className="btn secondary btn-sm"
          type="button"
          disabled={level === GROVE_LEVELS.length - 1}
          onClick={() => setLevelIndex(level + 1)}
        >
          →
        </button>
      </div>
      <label>
        Correct words / phrases
        <textarea rows={5} value={correctText} onChange={(e) => updateLevel("correct", e.target.value)} />
      </label>
      {textToWords(correctText).length > meta.correctMax ? (
        <p className="meta">Only the first {meta.correctMax} correct words are used in this level.</p>
      ) : null}
      <label>
        Incorrect words / phrases
        <textarea rows={5} value={wrongText} onChange={(e) => updateLevel("wrong", e.target.value)} />
      </label>
      {textToWords(wrongText).length > meta.wrongMax ? (
        <p className="meta">Only the first {meta.wrongMax} incorrect words are used in this level.</p>
      ) : null}
    </div>
  );
}
