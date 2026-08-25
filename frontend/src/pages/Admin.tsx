import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Game, type PlatformStats, type Role, type User } from "../api";

const TOPICS = ["ML", "Physics", "Math"] as const;

function primaryTopic(game: Game): string {
  return game.topic_tags?.find((t) => TOPICS.includes(t as (typeof TOPICS)[number])) || "ML";
}

export function AdminPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [games, setGames] = useState<Game[]>([]);
  const [stats, setStats] = useState<PlatformStats | null>(null);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);

  async function load() {
    const [u, s, g] = await Promise.all([
      api<User[]>("/api/admin/users"),
      api<PlatformStats>("/api/admin/stats"),
      api<Game[]>("/api/games"),
    ]);
    setUsers(u);
    setStats(s);
    setGames(g);
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
  }, []);

  async function setRole(userId: string, role: Role) {
    await api(`/api/admin/users/${userId}/role`, {
      method: "PATCH",
      body: JSON.stringify({ role }),
    });
    await load();
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

  return (
    <div>
      <section className="hero">
        <h1>Admin</h1>
        <p>Manage roles, review activity, and delete games.</p>
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
                    <Link to={`/play/${g.id}`}>{g.title}</Link>
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

      <div className="panel">
        <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>Users</h2>
        <table className="table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Email</th>
              <th>Role</th>
              <th>Change</th>
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
                    <option value="creator">creator</option>
                    <option value="admin">admin</option>
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
