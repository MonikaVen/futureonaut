import { useEffect, useMemo, useState } from "react";
import { api, type Game } from "../api";
import { GameCard } from "../GameCard";
import { ContinuePlaying } from "../ContinuePlaying";
import { useLanguage } from "../language";

const TOPICS = ["AI", "Physics", "Math"] as const;

const AI_FOCUS_LABELS = [
  "Computer Vision",
  "Large Language Models",
  "Transformers",
  "Privacy",
  "Cybersecurity",
  "Trustworthiness of AI",
] as const;

function primaryTopic(game: Game): (typeof TOPICS)[number] {
  const hit = game.topic_tags?.find((t) =>
    TOPICS.includes(t as (typeof TOPICS)[number])
  );
  if (hit) return hit as (typeof TOPICS)[number];
  if (game.topic_tags?.includes("ML")) return "AI";
  return "AI";
}

function focusLabels(game: Game): string[] {
  return (game.topic_tags || []).filter((t) =>
    AI_FOCUS_LABELS.includes(t as (typeof AI_FOCUS_LABELS)[number])
  );
}

type SortKey = "recent" | "popular" | "level-asc" | "level-desc" | "title";

function popularityScore(game: Game): number {
  return (
    (game.view_count ?? 0) * 2 +
    (game.like_count ?? 0) * 3 +
    (game.comment_count ?? 0)
  );
}

function sortGames(list: Game[], sort: SortKey): Game[] {
  const sorted = [...list];
  sorted.sort((a, b) => {
    if (sort === "title") return a.title.localeCompare(b.title);
    if (sort === "recent") {
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    }
    if (sort === "popular") {
      return (
        popularityScore(b) - popularityScore(a) ||
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );
    }
    if (sort === "level-desc") {
      return b.difficulty - a.difficulty || a.title.localeCompare(b.title);
    }
    return a.difficulty - b.difficulty || a.title.localeCompare(b.title);
  });
  return sorted;
}

export function CatalogPage() {
  const { t } = useLanguage();
  const [games, setGames] = useState<Game[]>([]);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [topic, setTopic] = useState<"All" | (typeof TOPICS)[number]>("All");
  const [level, setLevel] = useState<"All" | "1" | "2" | "3" | "4" | "5">("All");
  const [sort, setSort] = useState<SortKey>("recent");

  useEffect(() => {
    api<Game[]>("/api/games")
      .then(setGames)
      .catch((err) => setError(err.message));
  }, []);

  function patchGame(id: string, patch: Partial<Game>) {
    setGames((prev) => prev.map((g) => (g.id === id ? { ...g, ...patch } : g)));
  }

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    let list = [...games];
    if (q) {
      list = list.filter((g) => {
        const hay = [g.title, g.description, ...(g.topic_tags || [])].join(" ").toLowerCase();
        return hay.includes(q);
      });
    }
    if (topic !== "All") {
      list = list.filter((g) => primaryTopic(g) === topic);
    }
    if (level !== "All") {
      list = list.filter((g) => g.difficulty === Number(level));
    }
    return sortGames(list, sort);
  }, [games, query, topic, level, sort]);

  return (
    <div>
      <section className="hero">
        <h1>{t("games")}</h1>
        <p>{t("catalogLede")}</p>
      </section>
      {error && <div className="error">{error}</div>}

      <ContinuePlaying />

      <div className="topic-tabs" role="tablist" aria-label={t("topic")}>
        {(["All", ...TOPICS] as const).map((tp) => (
          <button
            key={tp}
            type="button"
            role="tab"
            aria-selected={topic === tp}
            className={`topic-tab${topic === tp ? " active" : ""}`}
            onClick={() => setTopic(tp)}
          >
            {tp === "All" ? t("all") : tp}
          </button>
        ))}
      </div>

      <div className="filters">
        <label className="filter-search">
          {t("search")}
          <input
            type="search"
            value={query}
            placeholder={t("search")}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        <label>
          {t("level")}
          <select value={level} onChange={(e) => setLevel(e.target.value as typeof level)}>
            <option value="All">{t("all")}</option>
            {[1, 2, 3, 4, 5].map((n) => (
              <option key={n} value={String(n)}>
                {n}
              </option>
            ))}
          </select>
        </label>
        <label>
          {t("sort")}
          <select value={sort} onChange={(e) => setSort(e.target.value as SortKey)}>
            <option value="recent">{t("recent")}</option>
            <option value="popular">{t("popular")}</option>
            <option value="level-asc">{t("levelAsc")}</option>
            <option value="level-desc">{t("levelDesc")}</option>
            <option value="title">{t("titleSort")}</option>
          </select>
        </label>
        <span className="meta filters-count">
          {visible.length} / {games.length}
        </span>
      </div>

      <div className="grid">
        {visible.map((g) => (
          <GameCard
            key={g.id}
            game={g}
            topic={primaryTopic(g)}
            focusLabels={focusLabels(g)}
            onUpdate={(patch) => patchGame(g.id, patch)}
          />
        ))}
        {!visible.length && !error && <p className="meta">{t("noGamesMatch")}</p>}
      </div>
    </div>
  );
}
