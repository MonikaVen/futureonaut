export type GroveWordLevel = {
  correct: string[];
  wrong: string[];
};

export type GroveConfig = {
  lessonName: string;
  requireTrash: boolean;
  levels: GroveWordLevel[];
};

export type GroveLevelMeta = {
  name: string;
  correctMax: number;
  wrongMax: number;
};

export const GRAMMAR_GROVE_TITLE = "Grammar Grove";
export const GROVE_CONFIG_LIMIT = 8000;

export const GROVE_LEVELS: GroveLevelMeta[] = [
  { name: "Level 1 · Whispering Roots", correctMax: 5, wrongMax: 4 },
  { name: "Level 2 · Mooncap Canopy", correctMax: 5, wrongMax: 5 },
  { name: "Level 3 · Starlit Hollow", correctMax: 6, wrongMax: 6 },
  { name: "Level 4 · Firefly Library", correctMax: 6, wrongMax: 6 },
  { name: "Level 5 · Aurora Crown", correctMax: 6, wrongMax: 6 },
  { name: "Level 6 · Cloudroot Ruins", correctMax: 6, wrongMax: 6 },
  { name: "Level 7 · Crystal Observatory", correctMax: 6, wrongMax: 6 },
  { name: "Level 8 · Heart of Grammar Grove", correctMax: 7, wrongMax: 7 },
];

const DEFAULT_LEVELS: GroveWordLevel[] = [
  { correct: ["went", "children", "better", "brought", "were"], wrong: ["goed", "childs", "gooder", "bringed"] },
  { correct: ["does", "mice", "fewer", "has", "best"], wrong: ["do", "mouses", "lesser", "have", "bestest"] },
  {
    correct: ["their", "could've", "than", "its", "lying", "who"],
    wrong: ["there", "could of", "then", "it's", "laying", "whom"],
  },
  {
    correct: ["because", "doesn't", "too", "your", "their", "were"],
    wrong: ["becuz", "dont", "to", "you're", "there", "was"],
  },
  {
    correct: ["would have", "fewer", "whose", "affect", "then", "you're"],
    wrong: ["would of", "less", "who's", "effect", "than", "your"],
  },
  {
    correct: ["ran", "teeth", "better", "bought", "many", "their"],
    wrong: ["runned", "tooths", "more better", "buyed", "much", "there"],
  },
  {
    correct: ["seen", "fewer", "whose", "accept", "then", "you're"],
    wrong: ["sawen", "less", "who's", "except", "than", "your"],
  },
  {
    correct: ["had gone", "children", "fewer", "its", "lying", "whom", "would have"],
    wrong: ["had went", "childs", "less", "it's", "laying", "who", "would of"],
  },
];

export function isGrammarGrove(title: string | undefined | null): boolean {
  return (title || "").trim().toLowerCase() === GRAMMAR_GROVE_TITLE.toLowerCase();
}

export function defaultGrammarGroveConfig(): GroveConfig {
  return {
    lessonName: GRAMMAR_GROVE_TITLE,
    requireTrash: true,
    levels: DEFAULT_LEVELS.map((level) => ({
      correct: [...level.correct],
      wrong: [...level.wrong],
    })),
  };
}

function takeWords(value: unknown, max: number): string[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => String(item).trim())
    .filter(Boolean)
    .slice(0, max);
}

export function parseGrammarGroveConfig(raw: string): GroveConfig {
  const base = defaultGrammarGroveConfig();
  const text = raw.trim();
  if (!text) return base;
  try {
    const data = JSON.parse(text) as Partial<GroveConfig>;
    if (!data || !Array.isArray(data.levels)) return base;
    return {
      lessonName: String(data.lessonName || base.lessonName).trim().slice(0, 70) || base.lessonName,
      requireTrash: data.requireTrash !== false,
      levels: base.levels.map((fallback, index) => {
        const set = data.levels?.[index];
        const meta = GROVE_LEVELS[index];
        if (!set) return { correct: [...fallback.correct], wrong: [...fallback.wrong] };
        return {
          correct: takeWords(set.correct, meta.correctMax),
          wrong: takeWords(set.wrong, meta.wrongMax),
        };
      }),
    };
  } catch {
    return base;
  }
}

export function serializeGrammarGroveConfig(config: GroveConfig): string {
  return JSON.stringify({
    lessonName: config.lessonName.trim() || GRAMMAR_GROVE_TITLE,
    requireTrash: config.requireTrash !== false,
    levels: config.levels.map((level, index) => ({
      correct: takeWords(level.correct, GROVE_LEVELS[index].correctMax),
      wrong: takeWords(level.wrong, GROVE_LEVELS[index].wrongMax),
    })),
  });
}

export function grammarGroveConfigError(raw: string): string {
  const config = parseGrammarGroveConfig(raw);
  for (let index = 0; index < config.levels.length; index += 1) {
    if (!config.levels[index].correct.length) return `Level ${index + 1} needs at least one correct word.`;
    if (!config.levels[index].wrong.length) return `Level ${index + 1} needs at least one incorrect word.`;
  }
  if (serializeGrammarGroveConfig(config).length > GROVE_CONFIG_LIMIT) {
    return "These word lists are too long to save on a class issue.";
  }
  return "";
}

/** Lesson title for a Grammar Grove class config. Raw JSON stays hidden so answers are not listed. */
export function groveLessonName(raw: string): string | null {
  const text = raw.trim();
  if (!text.startsWith("{")) return null;
  try {
    const data = JSON.parse(text) as { lessonName?: unknown; levels?: unknown };
    if (!Array.isArray(data.levels)) return null;
    const name = String(data.lessonName || "").trim();
    return name || "Custom word lists";
  } catch {
    return null;
  }
}

export function classIssueNote(raw: string): string {
  return groveLessonName(raw) ?? raw;
}
