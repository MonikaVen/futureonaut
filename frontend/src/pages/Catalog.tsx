import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Game } from "../api";
import { useLanguage } from "../language";

const TOPICS = ["ML", "Physics", "Math"] as const;

function primaryTopic(game: Game): string {
  const hit = game.topic_tags?.find((t) => TOPICS.includes(t as (typeof TOPICS)[number]));
  return hit || "ML";
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
        <p>Search, filter by topic and level. Games translate to your selected language.</p>
      </section>
      {error && <div className="error">{error}</div>}

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
          {t("topic")}
          <select value={topic} onChange={(e) => setTopic(e.target.value as typeof topic)}>
            <option value="All">All</option>
            {TOPICS.map((tp) => (
              <option key={tp} value={tp}>
                {tp}
              </option>
            ))}
          </select>
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
              <span className="tag">{primaryTopic(g)}</span>
              <span className="tag">Lv {g.difficulty}</span>
              <span className="tag">
                {t("detected")}: {(g.source_language || "en").toUpperCase()}
              </span>
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
