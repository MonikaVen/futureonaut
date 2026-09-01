import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Game } from "../api";
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

export function CatalogPage() {
  const { t } = useLanguage();
  const [games, setGames] = useState<Game[]>([]);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [topic, setTopic] = useState<"All" | (typeof TOPICS)[number]>("All");
  const [level, setLevel] = useState<"All" | "1" | "2" | "3" | "4" | "5">("All");
  const [sort, setSort] = useState<"level-asc" | "level-desc" | "title">("level-asc");

  useEffect(() => {
    api<Game[]>("/api/games")
      .then(setGames)
      .catch((err) => setError(err.message));
  }, []);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    let list = [...games];
    if (q) {
      list = list.filter((g) => {
        const hay = [
          g.title,
          g.description,
          g.source_language || "",
          ...(g.topic_tags || []),
        ]
          .join(" ")
          .toLowerCase();
        return hay.includes(q);
      });
    }
    if (topic !== "All") {
      list = list.filter((g) => primaryTopic(g) === topic);
    }
    if (level !== "All") {
      list = list.filter((g) => g.difficulty === Number(level));
    }
    list.sort((a, b) => {
      if (sort === "title") return a.title.localeCompare(b.title);
      if (sort === "level-desc") {
        return b.difficulty - a.difficulty || a.title.localeCompare(b.title);
      }
      return a.difficulty - b.difficulty || a.title.localeCompare(b.title);
    });
    return list;
  }, [games, query, topic, level, sort]);

  return (
    <div>
      <section className="hero">
        <h1>{t("games")}</h1>
        <p>Search and play without an account. Sign in to save scores and recommendations.</p>
      </section>
      {error && <div className="error">{error}</div>}

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
            {tp}
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
            <option value="All">All</option>
            {[1, 2, 3, 4, 5].map((n) => (
              <option key={n} value={String(n)}>
                {n}
              </option>
            ))}
          </select>
        </label>
        <label>
          {t("sort")}
          <select value={sort} onChange={(e) => setSort(e.target.value as typeof sort)}>
            <option value="level-asc">Level ↑</option>
            <option value="level-desc">Level ↓</option>
            <option value="title">Title</option>
          </select>
        </label>
        <span className="meta filters-count">
          {visible.length} of {games.length}
        </span>
      </div>

      <div className="grid">
        {visible.map((g) => (
          <article key={g.id} className="game-tile">
            <h3>{g.title}</h3>
            <p className="meta">{g.description || "No description"}</p>
            <div className="tags">
              <span className="tag topic">{primaryTopic(g)}</span>
              {focusLabels(g).map((label) => (
                <span key={label} className="tag focus">
                  {label}
                </span>
              ))}
              <span className="tag">Lv {g.difficulty}</span>
            </div>
            <div className="row">
              <Link className="btn accent" to={`/play/${g.id}`}>
                {t("play")}
              </Link>
            </div>
          </article>
        ))}
        {!visible.length && !error && <p className="meta">No games match these filters.</p>}
      </div>
    </div>
  );
}
