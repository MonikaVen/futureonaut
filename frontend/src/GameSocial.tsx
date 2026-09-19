import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Comment, type Game, type LikeToggle } from "./api";
import { AvatarImage } from "./AvatarImage";
import { useAuth } from "./auth";
import { GameShare } from "./GameShare";
import { CommentIcon, PlayIcon, StarIcon } from "./Icons";
import { useLanguage } from "./language";

type Props = {
  game: Game;
  onUpdate: (patch: Partial<Pick<Game, "like_count" | "comment_count" | "liked_by_me">>) => void;
  showComments?: boolean;
  compact?: boolean;
  shareTitle?: string;
  shareDescription?: string;
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

export function GameSocial({
  game,
  onUpdate,
  showComments = false,
  compact = false,
  shareTitle,
  shareDescription,
}: Props) {
  const { user } = useAuth();
  const { t } = useLanguage();
  const [comments, setComments] = useState<Comment[]>([]);
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [open, setOpen] = useState(showComments);
  const showShare = Boolean(shareTitle);

  useEffect(() => {
    setOpen(showComments);
  }, [showComments]);

  useEffect(() => {
    if (!open) return;
    api<Comment[]>(`/api/games/${game.id}/comments`)
      .then(setComments)
      .catch(() => setComments([]));
  }, [game.id, open, game.comment_count]);

  async function toggleFavourite() {
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
      onUpdate({ comment_count: (game.comment_count ?? 0) + 1 });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={`social${compact ? " compact" : ""}${open ? " with-comments" : ""}`}>
      <div className={`social-actions${showShare ? " social-actions-row" : ""}`}>
        <div className="social-actions-left">
          {user ? (
            <button
              type="button"
              className={`social-btn favourite${game.liked_by_me ? " active" : ""}`}
              disabled={busy}
              onClick={toggleFavourite}
              aria-pressed={game.liked_by_me}
              title={game.liked_by_me ? t("removeFavourite") : t("addFavourite")}
            >
              <StarIcon filled={game.liked_by_me} />
              <span>{t("favourite")}</span>
            </button>
          ) : (
            <Link
              className="social-btn favourite"
              to="/login"
              title={t("signInToFavourite")}
            >
              <StarIcon />
              <span>{t("favourite")}</span>
            </Link>
          )}
          <button
            type="button"
            className={`social-chip${open ? " active" : ""}`}
            title={t("comments")}
            aria-pressed={open}
            onClick={() => setOpen((value) => !value)}
          >
            <CommentIcon />
            <span>{game.comment_count ?? 0}</span>
          </button>
          {!compact && (game.like_count ?? 0) > 0 && (
            <span className="social-count meta" title={t("favourite")}>
              {game.like_count} {t("saved")}
            </span>
          )}
        </div>
        {compact && (
          <div className="social-actions-right">
            <Link className="btn accent social-play-btn" to={game.handle ? `/play/${game.handle}` : `/play/${game.id}`}>
              <PlayIcon size={14} />
              <span>{t("play")}</span>
            </Link>
            {showShare && shareTitle && (
              <GameShare
                gameId={game.id}
                title={shareTitle}
                description={shareDescription}
                compact
              />
            )}
          </div>
        )}
        {!compact && showShare && shareTitle && (
          <GameShare
            gameId={game.id}
            title={shareTitle}
            description={shareDescription}
            compact
          />
        )}
      </div>

      {open && (
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
                {t("post")}
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
                  <AvatarImage userId={c.user_id} name={c.author_name} hasAvatar={Boolean(c.author_has_avatar)} size={28} />
                  {c.author_slug ? (
                    <Link to={`/u/${c.author_slug}`}>
                      <b>{c.author_name}</b>
                    </Link>
                  ) : (
                    <b>{c.author_name}</b>
                  )}
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
