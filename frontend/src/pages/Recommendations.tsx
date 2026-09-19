import { useEffect, useState } from "react";
import { api, type Recommendation } from "../api";
import { GameCard } from "../GameCard";
import { primaryTopic } from "../gameMeta";

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
          <GameCard
            key={r.game.id}
            game={r.game}
            topic={primaryTopic(r.game.topic_tags)}
            reason={r.reason}
          />
        ))}
      </div>
    </div>
  );
}
