import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Comment, type Game, type LikeToggle } from "./api";
import { useAuth } from "./auth";
import { useLanguage } from "./language";

type Props = {
  game: Game;
  onUpdate: (patch: Partial<Pick<Game, "like_count" | "comment_count" | "liked_by_me">>) => void;
  showComments?: boolean;
  compact?: boolean;
};

function formatWhen(iso: string) {
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function GameSocial({ game, onUpdate, showComments = false, compact = false }: Props) {
  const { user } = useAuth();
  const { t } = useLanguage();
  const [comments, setComments] = useState<Comment[]>([]);
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!showComments) return;
    api<Comment[]>(`/api/games/${game.id}/comments`)
      .then(setComments)
      .catch(() => setComments([]));
  }, [game.id, showComments, game.comment_count]);

  async function toggleLike() {
    if (!user) return;
    setBusy(true);
    setError("");
    try {
      const res = await api<LikeToggle>(`/api/games/${game.id}/like`, { method: "POST" });
      onUpdate({ like_count: res.like_count, liked_by_me: res.liked });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setBusy(false);
    }
  }

  async function submitComment(e: React.FormEvent) {
    e.preventDefault();
    if (!user || !body.trim()) return;
    setBusy(true);
    setError("");
    try {
      const comment = await api<Comment>(`/api/games/${game.id}/comments`, {
        method: "POST",
        body: JSON.stringify({ body: body.trim() }),
      });
      setComments((prev) => [comment, ...prev]);
      setBody("");
      onUpdate({ comment_count: game.comment_count + 1 });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={`social${compact ? " compact" : ""}${showComments ? " with-comments" : ""}`}>
      <div className="social-actions">
        {user ? (
          <button
            type="button"
            className={`social-btn like${game.liked_by_me ? " active" : ""}`}
            disabled={busy}
            onClick={toggleLike}
            aria-pressed={game.liked_by_me}
          >
            ♥ {game.like_count}
          </button>
        ) : (
          <Link className="social-btn like" to="/login" title={t("signInToLike")}>
            ♥ {game.like_count}
          </Link>
        )}
        <span className="social-count" title={t("comments")}>
          💬 {game.comment_count}
        </span>
      </div>

      {showComments && (
        <div className="comments-panel">
          <h3 className="comments-title">{t("comments")}</h3>
          {error && <div className="error">{error}</div>}
          {user ? (
            <form className="comment-form" onSubmit={submitComment}>
              <textarea
                value={body}
                onChange={(e) => setBody(e.target.value)}
                placeholder={t("commentPlaceholder")}
                rows={3}
                maxLength={2000}
              />
              <button className="btn accent" type="submit" disabled={busy || !body.trim()}>
                {t("postComment")}
              </button>
            </form>
          ) : (
            <p className="meta">
              <Link to="/login">{t("signIn")}</Link> {t("signInToComment")}
            </p>
          )}
          <ul className="comment-list">
            {comments.map((c) => (
              <li key={c.id} className="comment-item">
                <div className="comment-meta">
                  <b>{c.author_name}</b>
                  <span className="meta">{formatWhen(c.created_at)}</span>
                </div>
                <p>{c.body}</p>
              </li>
            ))}
            {!comments.length && <li className="meta">{t("noComments")}</li>}
          </ul>
        </div>
      )}
    </div>
  );
}
