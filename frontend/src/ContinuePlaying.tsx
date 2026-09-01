import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type ContinueSession } from "./api";
import { useAuth } from "./auth";

export function ContinuePlaying() {
  const { user } = useAuth();
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
    <section className="continue-section panel">
      <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>Continue where you left off</h2>
      <div className="continue-grid">
        {items.map((item) => (
          <article key={item.session_id} className="continue-card">
            <h3>{item.game_title}</h3>
            <p className="meta">
              {item.total_points} pts
              {item.total_levels
                ? ` · Level ${item.levels_completed}/${item.total_levels}`
                : item.levels_completed
                  ? ` · Level ${item.levels_completed}`
                  : ""}
            </p>
            <Link className="btn accent" to={`/play/${item.game_id}`}>
              Continue
            </Link>
          </article>
        ))}
      </div>
    </section>
  );
}
