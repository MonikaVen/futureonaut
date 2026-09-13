import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Classroom, type ClassroomDetail, type Game } from "../api";
import { useAuth } from "../auth";

export function ClassroomPage() {
  const { user } = useAuth();
  const [classrooms, setClassrooms] = useState<Classroom[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ClassroomDetail | null>(null);
  const [games, setGames] = useState<Game[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [newName, setNewName] = useState("");
  const [joinCode, setJoinCode] = useState("");
  const [assignGameId, setAssignGameId] = useState("");

  async function loadClassrooms() {
    const list = await api<Classroom[]>("/api/classrooms/mine");
    setClassrooms(list);
    if (!selectedId && list.length) setSelectedId(list[0].id);
  }

  useEffect(() => {
    loadClassrooms().catch((err) => setError(err.message));
    api<Game[]>("/api/games")
      .then(setGames)
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    api<ClassroomDetail>(`/api/classrooms/${selectedId}`)
      .then(setDetail)
      .catch((err) => setError(err.message));
  }, [selectedId]);

  async function createClass(e: FormEvent) {
    e.preventDefault();
    setError("");
    setMessage("");
    try {
      const c = await api<Classroom>("/api/classrooms", {
        method: "POST",
        body: JSON.stringify({ name: newName }),
      });
      setNewName("");
      setMessage(`Class "${c.name}" created. Share code: ${c.join_code}`);
      await loadClassrooms();
      setSelectedId(c.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create class");
    }
  }

  async function joinClass(e: FormEvent) {
    e.preventDefault();
    setError("");
    setMessage("");
    try {
      const c = await api<Classroom>("/api/classrooms/join", {
        method: "POST",
        body: JSON.stringify({ code: joinCode }),
      });
      setJoinCode("");
      setMessage(`Joined "${c.name}"`);
      await loadClassrooms();
      setSelectedId(c.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invalid class code");
    }
  }

  async function assignGame(e: FormEvent) {
    e.preventDefault();
    if (!selectedId || !assignGameId) return;
    setError("");
    try {
      await api(`/api/classrooms/${selectedId}/assignments`, {
        method: "POST",
        body: JSON.stringify({ game_id: assignGameId }),
      });
      setMessage("Game assigned to class.");
      const d = await api<ClassroomDetail>(`/api/classrooms/${selectedId}`);
      setDetail(d);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Assign failed");
    }
  }

  async function refreshDetail() {
    if (!selectedId) return;
    const d = await api<ClassroomDetail>(`/api/classrooms/${selectedId}`);
    setDetail(d);
  }

  async function unassign(assignmentId: string) {
    if (!selectedId) return;
    setError("");
    try {
      await api(`/api/classrooms/${selectedId}/assignments/${assignmentId}`, { method: "DELETE" });
      setMessage("Assignment removed.");
      await refreshDetail();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unassign failed");
    }
  }

  async function leaveClass() {
    if (!selectedId) return;
    if (!confirm("Leave this class?")) return;
    setError("");
    try {
      await api(`/api/classrooms/${selectedId}/leave`, { method: "POST" });
      setMessage("You left the class.");
      setSelectedId(null);
      setDetail(null);
      await loadClassrooms();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Leave failed");
    }
  }

  async function deleteClass() {
    if (!selectedId) return;
    if (!confirm("Delete this class and its assignments?")) return;
    setError("");
    try {
      await api(`/api/classrooms/${selectedId}`, { method: "DELETE" });
      setMessage("Class deleted.");
      setSelectedId(null);
      setDetail(null);
      await loadClassrooms();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  }

  async function removeStudent(studentId: string) {
    if (!selectedId) return;
    if (!confirm("Remove this student from the class?")) return;
    setError("");
    try {
      await api(`/api/classrooms/${selectedId}/members/${studentId}`, { method: "DELETE" });
      setMessage("Student removed.");
      await refreshDetail();
      await loadClassrooms();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Remove failed");
    }
  }

  return (
    <div>
      <section className="hero">
        <h1>Classrooms</h1>
        <p>Create a class, share a join code, assign games, and track student progress.</p>
      </section>
      {error && <div className="error">{error}</div>}
      {message && <div className="panel" style={{ marginBottom: 12 }}>{message}</div>}

      <div className="classroom-layout">
        <aside className="panel classroom-sidebar">
          <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>Your classes</h2>
          {classrooms.length === 0 && <p className="meta">No classes yet.</p>}
          <ul className="class-list">
            {classrooms.map((c) => (
              <li key={c.id}>
                <button
                  type="button"
                  className={`class-pick${selectedId === c.id ? " active" : ""}`}
                  onClick={() => setSelectedId(c.id)}
                >
                  {c.name}
                </button>
              </li>
            ))}
          </ul>

          <form className="form" onSubmit={createClass}>
            <label>
              New class name
              <input value={newName} onChange={(e) => setNewName(e.target.value)} required />
            </label>
            <button className="btn accent" type="submit">
              Create class
            </button>
          </form>

          <form className="form" onSubmit={joinClass} style={{ marginTop: 16 }}>
            <label>
              Join with code
              <input
                value={joinCode}
                onChange={(e) => setJoinCode(e.target.value.toUpperCase())}
                placeholder="ABC123"
                required
              />
            </label>
            <button className="btn secondary" type="submit">
              Join class
            </button>
          </form>
        </aside>

        <div className="panel classroom-main">
          {!detail ? (
            <p className="meta">Select or create a class to get started.</p>
          ) : (
            <>
              <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
                <div>
                  <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>{detail.name}</h2>
                  <p className="meta">
                    {detail.member_count} members
                    {detail.is_teacher && detail.join_code !== "••••••" ? (
                      <> · Join code: <b>{detail.join_code}</b></>
                    ) : null}
                  </p>
                </div>
                <div className="row" style={{ gap: 8 }}>
                  {user?.id === detail.teacher_id && <span className="tag topic">Teacher</span>}
                  {detail.is_teacher ? (
                    <button className="btn danger btn-sm" type="button" onClick={deleteClass}>
                      Delete class
                    </button>
                  ) : (
                    <button className="btn secondary btn-sm" type="button" onClick={leaveClass}>
                      Leave class
                    </button>
                  )}
                </div>
              </div>

              <h3>Assignments</h3>
              {detail.assignments.length === 0 && <p className="meta">No games assigned yet.</p>}
              <ul className="assignment-list">
                {detail.assignments.map((a) => (
                  <li key={a.id} className="row" style={{ justifyContent: "space-between", gap: 8 }}>
                    <span>
                      {a.game_title}
                      <span className="meta" style={{ marginLeft: 8 }}>
                        {a.completed
                          ? `Done · ${a.points ?? 0} pts`
                          : a.points
                            ? `In progress · ${a.points} pts`
                            : "Not started"}
                      </span>
                    </span>
                    <span className="row" style={{ gap: 8 }}>
                      <Link className="btn accent btn-sm" to={`/play/${a.game_id}`}>
                        {a.completed ? "Replay" : "Play"}
                      </Link>
                      {detail.is_teacher && (
                        <button className="btn secondary btn-sm" type="button" onClick={() => unassign(a.id)}>
                          Remove
                        </button>
                      )}
                    </span>
                  </li>
                ))}
              </ul>

              {detail.is_teacher && (
                <form className="form row" onSubmit={assignGame} style={{ marginTop: 16 }}>
                  <label style={{ flex: 1 }}>
                    Assign game
                    <select value={assignGameId} onChange={(e) => setAssignGameId(e.target.value)} required>
                      <option value="">Choose a game…</option>
                      {games.map((g) => (
                        <option key={g.id} value={g.id}>
                          {g.title}
                        </option>
                      ))}
                    </select>
                  </label>
                  <button className="btn" type="submit" disabled={!assignGameId}>
                    Assign
                  </button>
                </form>
              )}

              {detail.is_teacher && detail.progress.length > 0 && (
                <>
                  <h3 style={{ marginTop: 24 }}>Student progress</h3>
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Student</th>
                        <th>Game</th>
                        <th>Status</th>
                        <th>Points</th>
                        <th>Accuracy</th>
                        <th>Levels</th>
                        <th />
                      </tr>
                    </thead>
                    <tbody>
                      {detail.progress.map((p, i) => (
                        <tr key={`${p.student_email}-${p.game_id}-${i}`}>
                          <td>{p.student_name}</td>
                          <td>{p.game_title}</td>
                          <td>{p.completed ? "Done" : p.points ? "In progress" : "Not started"}</td>
                          <td>{p.points}</td>
                          <td>{(p.accuracy * 100).toFixed(0)}%</td>
                          <td>
                            {p.levels_completed}
                            {p.total_levels ? `/${p.total_levels}` : ""}
                          </td>
                          <td>
                            {detail.progress.findIndex((x) => x.student_id === p.student_id) === i && (
                              <button
                                className="btn secondary btn-sm"
                                type="button"
                                onClick={() => removeStudent(p.student_id)}
                              >
                                Remove
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
