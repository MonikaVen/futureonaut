import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Comment, type Game, type GameAnalytics, type GameAnalyticsDetail, type PlatformStats, type Role, type User } from "../api";
import { GameAnalyticsDetailPanel } from "../GameAnalyticsDetail";

const TOPICS = ["AI", "Physics", "Math"] as const;

type SortKey = "views" | "plays" | "avg_time_ms" | "avg_levels_completed" | "completion_rate" | "title";

function primaryTopic(game: Game): string {
  const hit = game.topic_tags?.find((t) => TOPICS.includes(t as (typeof TOPICS)[number]));
  if (hit) return hit;
  if (game.topic_tags?.includes("ML")) return "AI";
  return "AI";
}

function formatDuration(ms: number): string {
  if (ms <= 0) return "—";
  const sec = ms / 1000;
  if (sec < 60) return `${sec.toFixed(0)}s`;
  const min = Math.floor(sec / 60);
  const rem = Math.round(sec % 60);
  return `${min}m ${rem}s`;
}

function formatPercent(rate: number): string {
  if (rate <= 0) return "—";
  return `${Math.round(rate * 100)}%`;
}

export function AdminPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [games, setGames] = useState<Game[]>([]);
  const [comments, setComments] = useState<Comment[]>([]);
  const [analytics, setAnalytics] = useState<GameAnalytics[]>([]);
  const [stats, setStats] = useState<PlatformStats | null>(null);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("views");
  const [detailId, setDetailId] = useState<string | null>(null);
  const [detail, setDetail] = useState<GameAnalyticsDetail | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");

  async function load() {
    const [u, s, g, a, c] = await Promise.all([
      api<User[]>("/api/admin/users"),
      api<PlatformStats>("/api/admin/stats"),
      api<Game[]>("/api/games"),
      api<GameAnalytics[]>("/api/admin/game-analytics"),
      api<Comment[]>("/api/admin/comments"),
    ]);
    setUsers(u);
    setStats(s);
    setGames(g);
    setAnalytics(a);
    setComments(c);
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
  }, []);

  const sortedAnalytics = useMemo(() => {
    const list = [...analytics];
    list.sort((a, b) => {
      if (sortKey === "title") return a.title.localeCompare(b.title);
      return (b[sortKey] as number) - (a[sortKey] as number);
    });
    return list;
  }, [analytics, sortKey]);

  async function setRole(userId: string, role: Role) {
    await api(`/api/admin/users/${userId}/role`, {
      method: "PATCH",
      body: JSON.stringify({ role }),
    });
    await load();
  }

  async function removeUser(u: User) {
    if (!confirm(`Delete ${u.display_name || u.email}? Their games stay in the catalog.`)) return;
    setBusyId(u.id);
    setError("");
    try {
      await api(`/api/admin/users/${u.id}`, { method: "DELETE" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setBusyId(null);
    }
  }

  async function deleteGame(game: Game) {
    if (!confirm(`Delete “${game.title}”? This also removes play sessions.`)) return;
    setBusyId(game.id);
    setError("");
    try {
      await api(`/api/games/${game.id}`, { method: "DELETE" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setBusyId(null);
    }
  }

  function startRename(game: Game) {
    setEditingId(game.id);
    setEditTitle(game.title);
  }

  async function saveTitle(game: Game) {
    const title = editTitle.trim();
    if (!title) {
      setError("Title is required");
      return;
    }
    setBusyId(game.id);
    setError("");
    try {
      await api(`/api/games/${game.id}`, {
        method: "PATCH",
        body: JSON.stringify({ title }),
      });
      setEditingId(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Rename failed");
    } finally {
      setBusyId(null);
    }
  }

  async function deleteComment(comment: Comment) {
    if (!confirm("Delete this comment?")) return;
    setBusyId(comment.id);
    setError("");
    try {
      await api(`/api/admin/comments/${comment.id}`, { method: "DELETE" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setBusyId(null);
    }
  }

  const gameTitle = (id: string) => games.find((g) => g.id === id)?.title || id.slice(0, 8);

  return (
    <div>
      <section className="hero">
        <h1>Admin</h1>
        <p>Curate the catalog stored in the database. Rename or delete games — the seed pack is not restored on redeploy.</p>
      </section>
      {error && <div className="error">{error}</div>}
      {stats && (
        <div className="stats">
          <div className="stat">
            <span className="meta">Users</span>
            <b>{stats.users}</b>
          </div>
          <div className="stat">
            <span className="meta">Creators</span>
            <b>{stats.creators}</b>
          </div>
          <div className="stat">
            <span className="meta">Learners</span>
            <b>{stats.learners}</b>
          </div>
          <div className="stat">
            <span className="meta">Games</span>
            <b>{stats.games}</b>
          </div>
          <div className="stat">
            <span className="meta">Sessions</span>
            <b>{stats.sessions}</b>
          </div>
        </div>
      )}

      <div className="panel section-gap">
        <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
          <h2 style={{ fontFamily: "var(--font-display)", margin: 0 }}>Game popularity</h2>
          <label className="meta">
            Sort by{" "}
            <select value={sortKey} onChange={(e) => setSortKey(e.target.value as SortKey)}>
              <option value="views">Views</option>
              <option value="plays">Plays</option>
              <option value="avg_time_ms">Avg time</option>
              <option value="avg_levels_completed">Avg levels</option>
              <option value="completion_rate">Completion</option>
              <option value="title">Title</option>
            </select>
          </label>
        </div>
        <p className="meta">
          Views count every play-page open (guests included). Plays, time, levels, and completion
          come from sessions tracked via the SDK. Click a row for the funnel and recent sessions.
        </p>
        <table className="table">
          <thead>
            <tr>
              <th>Title</th>
              <th>Topic</th>
              <th>Views</th>
              <th>Plays</th>
              <th>Players</th>
              <th>Avg time</th>
              <th>Avg levels</th>
              <th>Completion</th>
            </tr>
          </thead>
          <tbody>
            {sortedAnalytics.map((row) => (
              <tr
                key={row.game_id}
                className={detailId === row.game_id ? "row-selected" : ""}
                style={{ cursor: "pointer" }}
                onClick={() => {
                  setDetailId(row.game_id);
                  api<GameAnalyticsDetail>(`/api/admin/game-analytics/${row.game_id}`)
                    .then(setDetail)
                    .catch((err) => setError(err.message));
                }}
              >
                <td>
                  <Link to={`/play/${row.game_id}`} onClick={(e) => e.stopPropagation()}>
                    {row.title}
                  </Link>
                </td>
                <td>{row.topic}</td>
                <td>{row.views}</td>
                <td>{row.plays}</td>
                <td>{row.unique_players}</td>
                <td>{formatDuration(row.avg_time_ms)}</td>
                <td>{row.avg_levels_completed > 0 ? row.avg_levels_completed.toFixed(1) : "—"}</td>
                <td>{formatPercent(row.completion_rate)}</td>
              </tr>
            ))}
            {!sortedAnalytics.length && (
              <tr>
                <td colSpan={8} className="meta">
                  No analytics yet. Open a game to record views.
                </td>
              </tr>
            )}
          </tbody>
        </table>
        {detail && detailId === detail.game_id && (
          <GameAnalyticsDetailPanel
            detail={detail}
            onClose={() => {
              setDetail(null);
              setDetailId(null);
            }}
          />
        )}
      </div>

      <div className="panel section-gap">
        <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>Games</h2>
        <table className="table">
          <thead>
            <tr>
              <th>Title</th>
              <th>Topic</th>
              <th>Level</th>
              <th>Source</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {[...games]
              .sort((a, b) => a.difficulty - b.difficulty || a.title.localeCompare(b.title))
              .map((g) => (
                <tr key={g.id}>
                  <td>
                    {editingId === g.id ? (
                      <form
                        className="admin-rename"
                        onSubmit={(e) => {
                          e.preventDefault();
                          void saveTitle(g);
                        }}
                      >
                        <input
                          value={editTitle}
                          onChange={(e) => setEditTitle(e.target.value)}
                          maxLength={200}
                          autoFocus
                          aria-label="Game title"
                        />
                        <button className="btn accent btn-sm" type="submit" disabled={busyId === g.id}>
                          Save
                        </button>
                        <button
                          className="btn secondary btn-sm"
                          type="button"
                          onClick={() => setEditingId(null)}
                        >
                          Cancel
                        </button>
                      </form>
                    ) : (
                      <>
                        <Link to={g.handle ? `/play/${g.handle}` : `/play/${g.id}`}>{g.title}</Link>
                        <button
                          className="btn secondary btn-sm"
                          type="button"
                          onClick={() => startRename(g)}
                        >
                          Rename
                        </button>
                      </>
                    )}
                  </td>
                  <td>{primaryTopic(g)}</td>
                  <td>{g.difficulty}</td>
                  <td>{g.source}</td>
                  <td>
                    <button
                      className="btn danger"
                      type="button"
                      disabled={busyId === g.id}
                      onClick={() => deleteGame(g)}
                    >
                      {busyId === g.id ? "Deleting…" : "Delete"}
                    </button>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>

      <div className="panel section-gap">
        <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>Comments</h2>
        <table className="table">
          <thead>
            <tr>
              <th>Game</th>
              <th>Author</th>
              <th>Comment</th>
              <th>When</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {comments.map((c) => (
              <tr key={c.id}>
                <td>
                  <Link to={`/play/${c.game_id}`}>{gameTitle(c.game_id)}</Link>
                </td>
                <td>{c.author_name}</td>
                <td>{c.body}</td>
                <td className="meta">{new Date(c.created_at).toLocaleString()}</td>
                <td>
                  <button
                    className="btn danger"
                    type="button"
                    disabled={busyId === c.id}
                    onClick={() => deleteComment(c)}
                  >
                    {busyId === c.id ? "…" : "Delete"}
                  </button>
                </td>
              </tr>
            ))}
            {!comments.length && (
              <tr>
                <td colSpan={5} className="meta">
                  No comments yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="panel">
        <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>Users</h2>
        <table className="table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Email</th>
              <th>Role</th>
              <th>Change</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td>{u.display_name}</td>
                <td>{u.email}</td>
                <td>{u.role}</td>
                <td>
                  <select
                    value={u.role}
                    onChange={(e) => setRole(u.id, e.target.value as Role)}
                  >
                    <option value="learner">learner</option>
                    <option value="teacher">teacher</option>
                    <option value="creator">creator</option>
                    <option value="admin">admin</option>
                  </select>
                </td>
                <td>
                  <button
                    className="btn danger btn-sm"
                    type="button"
                    disabled={busyId === u.id}
                    onClick={() => removeUser(u)}
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
