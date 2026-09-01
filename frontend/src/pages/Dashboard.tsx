import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type DashboardStats } from "../api";
import { ContinuePlaying } from "../ContinuePlaying";

export function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<DashboardStats>("/api/dashboard")
      .then(setStats)
      .catch((err) => setError(err.message));
  }, []);

  if (error) return <div className="error">{error}</div>;
  if (!stats) return <p className="meta">Loading dashboard…</p>;

  return (
    <div>
      <section className="hero">
        <h1>Your progress</h1>
        <p>Scores, accuracy, and time across everything you have played.</p>
      </section>
      <ContinuePlaying />
      <div className="stats" style={{ marginBottom: 18 }}>
        <div className="stat">
          <span className="meta">Sessions</span>
          <b>{stats.total_sessions}</b>
        </div>
        <div className="stat">
          <span className="meta">Points</span>
          <b>{stats.total_points}</b>
        </div>
        <div className="stat">
          <span className="meta">Avg accuracy</span>
          <b>{(stats.avg_accuracy * 100).toFixed(0)}%</b>
        </div>
        <div className="stat">
          <span className="meta">Avg task time</span>
          <b>{(stats.avg_task_time_ms / 1000).toFixed(1)}s</b>
        </div>
      </div>

      <div className="panel" style={{ marginBottom: 16 }}>
        <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>By topic</h2>
        {stats.by_topic.length === 0 && <p className="meta">Play games to unlock topic insights.</p>}
        <table className="table">
          <thead>
            <tr>
              <th>Topic</th>
              <th>Sessions</th>
              <th>Accuracy</th>
              <th>Points</th>
            </tr>
          </thead>
          <tbody>
            {stats.by_topic.map((t) => (
              <tr key={String(t.topic)}>
                <td>{String(t.topic)}</td>
                <td>{String(t.sessions)}</td>
                <td>{(Number(t.accuracy) * 100).toFixed(0)}%</td>
                <td>{String(t.points)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="panel">
        <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>Recent sessions</h2>
        <table className="table">
          <thead>
            <tr>
              <th>Game</th>
              <th>Points</th>
              <th>Accuracy</th>
              <th>Time</th>
            </tr>
          </thead>
          <tbody>
            {stats.recent_sessions.map((s) => (
              <tr key={s.id}>
                <td>
                  <Link to={`/play/${s.game_id}`}>{s.game_title || s.game_id}</Link>
                </td>
                <td>{s.total_points}</td>
                <td>
                  {s.attempt_count
                    ? `${((s.correct_count / s.attempt_count) * 100).toFixed(0)}%`
                    : "—"}
                </td>
                <td>{(s.total_time_ms / 1000).toFixed(1)}s</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
