import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type ContinueSession } from "./api";
import { useAuth } from "./auth";
import { GamePreview } from "./GamePreview";
import { primaryTopic } from "./gameMeta";
import { useLanguage } from "./language";

export function ContinuePlaying() {
  const { user } = useAuth();
  const { t } = useLanguage();
  const [items, setItems] = useState<ContinueSession[]>([]);

  useEffect(() => {
    if (!user) {
      setItems([]);
      return;
    }
    api<ContinueSession[]>("/api/sessions/continue")
      .then(setItems)
      .catch(() => setItems([]));
  }, [user]);

  if (!user || items.length === 0) return null;

  return (
    <section className="preview-card-section continue-section">
      <h2>{t("continueSection")}</h2>
      <div className="grid">
        {items.map((item) => {
          const progressPct =
            item.total_levels && item.total_levels > 0
              ? Math.round((item.levels_completed / item.total_levels) * 100)
              : null;
          const progressLabel = item.total_levels
            ? `${t("level")} ${item.levels_completed}/${item.total_levels}`
            : item.levels_completed
              ? `${t("level")} ${item.levels_completed}`
              : undefined;

          return (
            <article key={item.session_id} className="game-tile">
              <GamePreview
                gameId={item.game_id}
                title={item.game_title}
                description={item.game_description}
                topic={primaryTopic(item.topic_tags)}
                difficulty={item.difficulty ?? 1}
                progressLabel={progressLabel}
                progressPct={progressPct}
                hasScreenshot={Boolean(item.has_screenshot)}
              />
              <div className="game-tile-body continue-tile-body">
                <p className="meta">
                  {item.total_points} {t("pts")}
                  {progressLabel ? ` · ${progressLabel}` : ""}
                </p>
                <Link className="btn accent btn-sm" to={`/play/${item.game_id}`}>
                  {t("continue")}
                </Link>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
