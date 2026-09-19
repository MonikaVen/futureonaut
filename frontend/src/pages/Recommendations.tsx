import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Recommendation } from "../api";

export function RecommendationsPage() {
  const [items, setItems] = useState<Recommendation[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api<Recommendation[]>("/api/recommendations")
      .then(setItems)
      .catch((err) => setError(err.message));
  }, []);

  return (
    <div>
      <section className="hero">
        <h1>For you</h1>
        <p>Suggested from weak topics, new games, and a gentle difficulty ramp.</p>
      </section>
      {error && <div className="error">{error}</div>}
      <div className="grid">
        {items.map((r) => (
          <article key={r.game.id} className="game-tile">
            <h3>{r.game.title}</h3>
            {r.game.owner_name && <p className="meta">by {r.game.owner_name}</p>}
            <p className="meta">{r.reason}</p>
            <div className="tags">
              <span className="tag">Lv {r.game.difficulty}</span>
              {r.game.topic_tags?.map((t) => (
                <span className="tag" key={t}>
                  {t}
                </span>
              ))}
            </div>
            <Link className="btn accent" to={`/play/${r.game.id}`}>
              Play
            </Link>
          </article>
        ))}
      </div>
    </div>
  );
}
