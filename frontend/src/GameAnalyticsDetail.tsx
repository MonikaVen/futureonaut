import type { GameAnalyticsDetail } from "./api";

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

type Props = {
  detail: GameAnalyticsDetail;
  onClose: () => void;
};

export function GameAnalyticsDetailPanel({ detail, onClose }: Props) {
  return (
    <div className="analytics-detail">
      <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h3 style={{ fontFamily: "var(--font-display)", margin: "0 0 0.25rem" }}>{detail.title}</h3>
          <p className="meta">
            {detail.topic} · Lv {detail.difficulty} · {detail.unique_visitors} unique visitors ·{" "}
            {formatPercent(detail.view_to_play_rate)} view→play
          </p>
        </div>
        <button className="btn secondary btn-sm" type="button" onClick={onClose}>
          Close
        </button>
      </div>

      <div className="stats" style={{ margin: "0.75rem 0" }}>
        <div className="stat">
          <span className="meta">Views</span>
          <b>{detail.views}</b>
        </div>
        <div className="stat">
          <span className="meta">Plays</span>
          <b>{detail.plays}</b>
        </div>
        <div className="stat">
          <span className="meta">Avg score</span>
          <b>{detail.avg_score.toFixed(0)}</b>
        </div>
        <div className="stat">
          <span className="meta">Accuracy</span>
          <b>{formatPercent(detail.avg_accuracy)}</b>
        </div>
        <div className="stat">
          <span className="meta">Avg time</span>
          <b>{formatDuration(detail.avg_time_ms)}</b>
        </div>
      </div>

      {detail.daily_views.length > 0 && (
        <>
          <h4 style={{ marginBottom: 8 }}>Views (14 days)</h4>
          <div className="view-bars" aria-label="Daily views">
            {detail.daily_views.map((day) => {
              const max = Math.max(...detail.daily_views.map((d) => d.views), 1);
              return (
                <div key={day.date} className="view-bar" title={`${day.date}: ${day.views}`}>
                  <span style={{ height: `${Math.max(8, (day.views / max) * 100)}%` }} />
                </div>
              );
            })}
          </div>
        </>
      )}

      {detail.level_funnel.length > 0 && (
        <>
          <h4>Level funnel</h4>
          <table className="table">
            <thead>
              <tr>
                <th>Level</th>
                <th>Reached</th>
                <th>Rate</th>
              </tr>
            </thead>
            <tbody>
              {detail.level_funnel.map((row) => (
                <tr key={row.level}>
                  <td>{row.level}</td>
                  <td>{row.sessions_reached}</td>
                  <td>{formatPercent(row.reach_rate)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {detail.task_stats.length > 0 && (
        <>
          <h4>Tasks</h4>
          <table className="table">
            <thead>
              <tr>
                <th>Task</th>
                <th>Completions</th>
                <th>Avg time</th>
              </tr>
            </thead>
            <tbody>
              {detail.task_stats.map((row) => (
                <tr key={row.task_id}>
                  <td>{row.task_id}</td>
                  <td>{row.completions}</td>
                  <td>{formatDuration(row.avg_duration_ms)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {detail.recent_sessions.length > 0 && (
        <>
          <h4>Recent sessions</h4>
          <table className="table">
            <thead>
              <tr>
                <th>Player</th>
                <th>Points</th>
                <th>Accuracy</th>
                <th>Levels</th>
                <th>Done</th>
              </tr>
            </thead>
            <tbody>
              {detail.recent_sessions.map((row) => (
                <tr key={row.session_id}>
                  <td>{row.user_email}</td>
                  <td>{row.points}</td>
                  <td>{formatPercent(row.accuracy)}</td>
                  <td>
                    {row.levels_completed}
                    {row.total_levels ? `/${row.total_levels}` : ""}
                  </td>
                  <td>{row.completed ? "Yes" : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}
