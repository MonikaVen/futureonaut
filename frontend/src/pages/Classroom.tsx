import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, type Classroom, type ClassroomDetail, type Game, type IssuedLogin } from "../api";
import { useAuth } from "../auth";
import { GrammarGroveConfigEditor } from "../components/GrammarGroveConfig";
import {
  classIssueNote,
  defaultGrammarGroveConfig,
  grammarGroveConfigError,
  isGrammarGrove,
  parseGrammarGroveConfig,
  serializeGrammarGroveConfig,
} from "../grammarGrove";

export function ClassroomPage() {
  const { user, refreshMe } = useAuth();
  const navigate = useNavigate();
  const [classrooms, setClassrooms] = useState<Classroom[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ClassroomDetail | null>(null);
  const [games, setGames] = useState<Game[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [newName, setNewName] = useState("");
  const [joinCode, setJoinCode] = useState("");
  const [assignGameId, setAssignGameId] = useState("");
  const [assignConfig, setAssignConfig] = useState("");
  const [assignPublished, setAssignPublished] = useState(true);
  const [configs, setConfigs] = useState<Record<string, string>>({});
  const [studentName, setStudentName] = useState("");
  const [studentEmail, setStudentEmail] = useState("");
  const [studentPassword, setStudentPassword] = useState("");
  const [studentGroup, setStudentGroup] = useState("");
  const [groupName, setGroupName] = useState("");
  const [issued, setIssued] = useState<IssuedLogin | null>(null);
  const [passwordDrafts, setPasswordDrafts] = useState<Record<string, string>>({});

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
      .then((d) => {
        setDetail(d);
        const next: Record<string, string> = {};
        for (const assignment of d.assignments) next[assignment.id] = assignment.config || "";
        setConfigs(next);
      })
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
      await refreshMe();
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
    const game = games.find((item) => item.id === assignGameId);
    const config = isGrammarGrove(game?.title)
      ? serializeGrammarGroveConfig(parseGrammarGroveConfig(assignConfig))
      : assignConfig;
    if (isGrammarGrove(game?.title)) {
      const problem = grammarGroveConfigError(config);
      if (problem) {
        setError(problem);
        return;
      }
    }
    setError("");
    try {
      await api(`/api/classrooms/${selectedId}/assignments`, {
        method: "POST",
        body: JSON.stringify({
          game_id: assignGameId,
          config,
          published: assignPublished,
        }),
      });
      setAssignConfig("");
      setAssignPublished(true);
      setMessage(assignPublished ? "Game published to the class." : "Game saved as a draft.");
      await refreshDetail();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Assign failed");
    }
  }

  async function refreshDetail() {
    if (!selectedId) return;
    const d = await api<ClassroomDetail>(`/api/classrooms/${selectedId}`);
    setDetail(d);
    const next: Record<string, string> = {};
    for (const assignment of d.assignments) next[assignment.id] = assignment.config || "";
    setConfigs(next);
  }

  function issueConfig(assignmentId: string, gameTitle: string) {
    const raw = configs[assignmentId] ?? "";
    if (!isGrammarGrove(gameTitle)) return raw;
    return serializeGrammarGroveConfig(parseGrammarGroveConfig(raw));
  }

  async function saveIssue(assignmentId: string, published?: boolean) {
    if (!selectedId || !detail) return;
    const assignment = detail.assignments.find((item) => item.id === assignmentId);
    const config = issueConfig(assignmentId, assignment?.game_title || "");
    if (isGrammarGrove(assignment?.game_title)) {
      const problem = grammarGroveConfigError(config);
      if (problem) {
        setError(problem);
        return;
      }
    }
    setError("");
    try {
      await api(`/api/classrooms/${selectedId}/assignments/${assignmentId}`, {
        method: "PATCH",
        body: JSON.stringify({
          config,
          ...(published === undefined ? {} : { published }),
        }),
      });
      setMessage(published === false ? "Issue unpublished." : "Class issue saved.");
      await refreshDetail();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the class issue");
    }
  }

  async function openTeacherView(assignmentId: string, gameId: string) {
    if (!selectedId || !detail) return;
    const assignment = detail.assignments.find((item) => item.id === assignmentId);
    const config = issueConfig(assignmentId, assignment?.game_title || "");
    if (isGrammarGrove(assignment?.game_title)) {
      const problem = grammarGroveConfigError(config);
      if (problem) {
        setError(problem);
        return;
      }
    }
    setError("");
    try {
      await api(`/api/classrooms/${selectedId}/assignments/${assignmentId}`, {
        method: "PATCH",
        body: JSON.stringify({ config }),
      });
      navigate(`/play/${gameId}?class=${selectedId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not open the teacher view");
    }
  }

  async function createStudent(e: FormEvent) {
    e.preventDefault();
    if (!selectedId) return;
    if (studentPassword && studentPassword.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setError("");
    try {
      const login = await api<IssuedLogin>(`/api/classrooms/${selectedId}/students`, {
        method: "POST",
        body: JSON.stringify({
          email: studentEmail,
          display_name: studentName,
          password: studentPassword || null,
          group_id: studentGroup || null,
        }),
      });
      setIssued(login);
      setStudentName("");
      setStudentEmail("");
      setStudentPassword("");
      setStudentGroup("");
      setMessage(`Login issued for ${login.display_name}. Copy it now — the password is not shown again.`);
      await refreshDetail();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create the student");
    }
  }

  async function resetPassword(studentId: string) {
    if (!selectedId) return;
    const password = (passwordDrafts[studentId] || "").trim();
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setError("");
    try {
      const login = await api<IssuedLogin>(`/api/classrooms/${selectedId}/students/${studentId}/password`, {
        method: "PATCH",
        body: JSON.stringify({ password }),
      });
      setIssued(login);
      setPasswordDrafts((prev) => ({ ...prev, [studentId]: "" }));
      setMessage(`Password updated for ${login.display_name}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update the password");
    }
  }

  async function createGroup(e: FormEvent) {
    e.preventDefault();
    if (!selectedId) return;
    setError("");
    try {
      await api(`/api/classrooms/${selectedId}/groups`, {
        method: "POST",
        body: JSON.stringify({ name: groupName }),
      });
      setGroupName("");
      setMessage("Group created.");
      await refreshDetail();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create the group");
    }
  }

  async function removeGroup(groupId: string) {
    if (!selectedId) return;
    if (!confirm("Delete this group? Students stay in the class.")) return;
    setError("");
    try {
      await api(`/api/classrooms/${selectedId}/groups/${groupId}`, { method: "DELETE" });
      setMessage("Group deleted.");
      await refreshDetail();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete the group");
    }
  }

  async function moveStudent(studentId: string, groupId: string) {
    if (!selectedId) return;
    setError("");
    try {
      await api(`/api/classrooms/${selectedId}/members/${studentId}`, {
        method: "PATCH",
        body: JSON.stringify({ group_id: groupId || null }),
      });
      await refreshDetail();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not move the student");
    }
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
        <p>
          Issue a game to a class with your own configuration. Students see it after you add them and publish it.
        </p>
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

          {user && (user.role === "teacher" || user.role === "admin" || user.role === "creator") ? (
          <form className="form" onSubmit={createClass}>
            <label>
              New class name
              <input value={newName} onChange={(e) => setNewName(e.target.value)} required />
            </label>
            <button className="btn accent" type="submit">
              Create class
            </button>
          </form>
          ) : null}

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
                  {detail.total_assignments ? (
                    <p className="class-progress-summary">
                      <span className="status-chip solved">
                        {detail.solved_assignments ?? 0}/{detail.total_assignments} solved
                      </span>
                      {detail.is_teacher ? (
                        <span className="meta">
                          {detail.students_solved_all ?? 0}/{detail.member_count} students finished every assignment
                        </span>
                      ) : null}
                    </p>
                  ) : null}
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

              <h3>Class issues</h3>
              {detail.assignments.length === 0 && <p className="meta">No games assigned yet.</p>}
              <ul className="assignment-list">
                {detail.assignments.map((a) => {
                  const status = a.completed ? "solved" : a.points || a.levels_completed ? "progress" : "idle";
                  const statusLabel =
                    status === "solved" ? "Solved" : status === "progress" ? "In progress" : "Not started";
                  const pct =
                    typeof a.progress_pct === "number"
                      ? a.progress_pct
                      : a.total_levels
                        ? Math.round(((a.levels_completed ?? 0) / a.total_levels) * 100)
                        : a.completed
                          ? 100
                          : 0;
                  return (
                    <li key={a.id} className="assignment-row">
                      <div className="assignment-main">
                        <span className="assignment-title">{a.game_title}</span>
                        <span className={`status-chip ${status}`}>{statusLabel}</span>
                        {a.levels_completed || a.total_levels ? (
                          <span className="meta">
                            Level {a.levels_completed ?? 0}
                            {a.total_levels ? `/${a.total_levels}` : ""}
                          </span>
                        ) : null}
                        {a.points ? <span className="meta">{a.points} pts</span> : null}
                        {detail.is_teacher ? (
                          <span className={`status-chip ${a.published === false ? "idle" : "solved"}`}>
                            {a.published === false ? "Draft" : "Published"}
                          </span>
                        ) : null}
                        {a.config ? <p className="meta class-issue-note">{classIssueNote(a.config)}</p> : null}
                        {detail.is_teacher && a.solved_count != null ? (
                          <span className="meta">
                            {a.solved_count}/{detail.member_count} solved
                          </span>
                        ) : null}
                        <span className="assignment-bar" aria-hidden>
                          <span style={{ width: `${pct}%` }} />
                        </span>
                      </div>
                      <span className="row" style={{ gap: 8 }}>
                        {detail.is_teacher && isGrammarGrove(a.game_title) ? (
                          <button
                            className="btn accent btn-sm"
                            type="button"
                            onClick={() => void openTeacherView(a.id, a.game_id)}
                          >
                            Teacher view
                          </button>
                        ) : (
                          <Link className="btn accent btn-sm" to={`/play/${a.game_id}?class=${detail.id}`}>
                            {detail.is_teacher ? "Teacher view" : a.completed ? "Replay" : "Play"}
                          </Link>
                        )}
                        {detail.is_teacher && (
                          <button className="btn secondary btn-sm" type="button" onClick={() => unassign(a.id)}>
                            Remove
                          </button>
                        )}
                      </span>
                    </li>
                  );
                })}
              </ul>

              {detail.is_teacher && (
                <form className="form" onSubmit={assignGame} style={{ marginTop: 16 }}>
                  <label>
                    Issue a game
                    <select
                      value={assignGameId}
                      onChange={(e) => {
                        const id = e.target.value;
                        setAssignGameId(id);
                        const picked = games.find((item) => item.id === id);
                        if (isGrammarGrove(picked?.title)) {
                          setAssignConfig(serializeGrammarGroveConfig(defaultGrammarGroveConfig()));
                        } else {
                          setAssignConfig("");
                        }
                      }}
                      required
                    >
                      <option value="">Choose a game…</option>
                      {games.map((g) => (
                        <option key={g.id} value={g.id}>
                          {g.title}
                        </option>
                      ))}
                    </select>
                  </label>
                  {isGrammarGrove(games.find((item) => item.id === assignGameId)?.title) ? (
                    <GrammarGroveConfigEditor value={assignConfig} onChange={setAssignConfig} />
                  ) : (
                    <label>
                      Configuration for this class
                      <textarea
                        rows={4}
                        value={assignConfig}
                        onChange={(e) => setAssignConfig(e.target.value)}
                        placeholder="Instructions, level, or JSON the game can read as LearnPlay.classConfig"
                      />
                    </label>
                  )}
                  <label className="row" style={{ gap: 8, alignItems: "center" }}>
                    <input
                      type="checkbox"
                      checked={assignPublished}
                      onChange={(e) => setAssignPublished(e.target.checked)}
                    />
                    Publish so students in this class can see it
                  </label>
                  <button className="btn" type="submit" disabled={!assignGameId}>
                    Issue to class
                  </button>
                </form>
              )}

              {detail.is_teacher &&
                detail.assignments.map((a) => (
                  <form
                    key={`cfg-${a.id}`}
                    className="form"
                    style={{ marginTop: 12 }}
                    onSubmit={(e) => {
                      e.preventDefault();
                      void saveIssue(a.id);
                    }}
                  >
                    {isGrammarGrove(a.game_title) ? (
                      <>
                        <h3 style={{ marginBottom: 0 }}>{a.game_title} word lists</h3>
                        <GrammarGroveConfigEditor
                          value={configs[a.id] ?? ""}
                          onChange={(next) => setConfigs((prev) => ({ ...prev, [a.id]: next }))}
                        />
                      </>
                    ) : (
                      <label>
                        {a.game_title} configuration
                        <textarea
                          rows={3}
                          value={configs[a.id] ?? ""}
                          onChange={(e) => setConfigs((prev) => ({ ...prev, [a.id]: e.target.value }))}
                        />
                      </label>
                    )}
                    <span className="row" style={{ gap: 8, flexWrap: "wrap" }}>
                      <button className="btn btn-sm" type="submit">
                        Save configuration
                      </button>
                      {isGrammarGrove(a.game_title) ? (
                        <button
                          className="btn accent btn-sm"
                          type="button"
                          onClick={() => void openTeacherView(a.id, a.game_id)}
                        >
                          Teacher view
                        </button>
                      ) : null}
                      <button
                        className="btn secondary btn-sm"
                        type="button"
                        onClick={() => void saveIssue(a.id, a.published === false)}
                      >
                        {a.published === false ? "Publish" : "Unpublish"}
                      </button>
                    </span>
                  </form>
                ))}

              {detail.is_teacher && (
                <>
                  <h3 style={{ marginTop: 24 }}>Groups</h3>
                  {(detail.groups || []).length === 0 && <p className="meta">No groups yet.</p>}
                  <ul className="assignment-list">
                    {(detail.groups || []).map((g) => (
                      <li key={g.id} className="assignment-row">
                        <div className="assignment-main">
                          <span className="assignment-title">{g.name}</span>
                          <span className="meta">{g.member_count} students</span>
                        </div>
                        <button className="btn secondary btn-sm" type="button" onClick={() => void removeGroup(g.id)}>
                          Delete
                        </button>
                      </li>
                    ))}
                  </ul>
                  <form className="form row" onSubmit={createGroup}>
                    <label style={{ flex: 1 }}>
                      New group
                      <input value={groupName} onChange={(e) => setGroupName(e.target.value)} required />
                    </label>
                    <button className="btn" type="submit">
                      Add group
                    </button>
                  </form>

                  <h3 style={{ marginTop: 24 }}>Students</h3>
                  {issued && (
                    <div className="panel" style={{ marginBottom: 12 }}>
                      <p>
                        <b>{issued.display_name}</b>
                      </p>
                      <p className="meta">Email: {issued.email}</p>
                      <p className="meta">Password: {issued.password}</p>
                    </div>
                  )}
                  {(detail.members || []).length === 0 && <p className="meta">No student accounts in this class yet.</p>}
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Student</th>
                        <th>Login</th>
                        <th>Group</th>
                        <th>New password</th>
                        <th />
                      </tr>
                    </thead>
                    <tbody>
                      {(detail.members || []).map((m) => (
                        <tr key={m.user_id}>
                          <td>{m.display_name}</td>
                          <td>{m.email}</td>
                          <td>
                            <select
                              value={m.group_id || ""}
                              onChange={(e) => void moveStudent(m.user_id, e.target.value)}
                            >
                              <option value="">No group</option>
                              {(detail.groups || []).map((g) => (
                                <option key={g.id} value={g.id}>
                                  {g.name}
                                </option>
                              ))}
                            </select>
                          </td>
                          <td>
                            <input
                              type="text"
                              value={passwordDrafts[m.user_id] || ""}
                              onChange={(e) =>
                                setPasswordDrafts((prev) => ({ ...prev, [m.user_id]: e.target.value }))
                              }
                              placeholder="At least 8 characters"
                            />
                          </td>
                          <td>
                            <button className="btn secondary btn-sm" type="button" onClick={() => void resetPassword(m.user_id)}>
                              Set password
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <form className="form" onSubmit={createStudent} style={{ marginTop: 16 }}>
                    <h3 style={{ marginBottom: 8 }}>Create a student login</h3>
                    <label>
                      Name
                      <input value={studentName} onChange={(e) => setStudentName(e.target.value)} required />
                    </label>
                    <label>
                      Email
                      <input
                        type="email"
                        value={studentEmail}
                        onChange={(e) => setStudentEmail(e.target.value)}
                        required
                      />
                    </label>
                    <label>
                      Password
                      <input
                        value={studentPassword}
                        onChange={(e) => setStudentPassword(e.target.value)}
                        placeholder="Leave blank to generate one"
                      />
                    </label>
                    <label>
                      Group
                      <select value={studentGroup} onChange={(e) => setStudentGroup(e.target.value)}>
                        <option value="">No group</option>
                        {(detail.groups || []).map((g) => (
                          <option key={g.id} value={g.id}>
                            {g.name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <button className="btn accent" type="submit">
                      Create student
                    </button>
                  </form>
                </>
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
                          <td>
                            <span className={`status-chip ${p.completed ? "solved" : p.points || p.levels_completed ? "progress" : "idle"}`}>
                              {p.completed ? "Solved" : p.points || p.levels_completed ? "In progress" : "Not started"}
                            </span>
                          </td>
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
