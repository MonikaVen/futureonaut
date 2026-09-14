import { useEffect, useState } from "react";
import { api, type Recommendation } from "../api";
import { GamePreview } from "../GamePreview";
import { primaryTopic } from "../gameMeta";
import { useLanguage } from "../language";

export function RecommendationsPage() {
  const { t } = useLanguage();
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
        <h1>{t("forYou")}</h1>
        <p>{t("forYouLede")}</p>
      </section>
      {error && <div className="error">{error}</div>}
      <section className="preview-card-section">
        <div className="grid">
          {items.map((r) => (
            <article key={r.game.id} className="game-tile">
              <GamePreview
                gameId={r.game.id}
                title={r.game.title}
                description={r.game.description}
                topic={primaryTopic(r.game.topic_tags)}
                difficulty={r.game.difficulty}
              />
              <div className="game-tile-body">
                <p className="meta">{r.reason}</p>
              </div>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
