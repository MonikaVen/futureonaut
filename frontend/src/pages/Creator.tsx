import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Game } from "../api";

const QUIZ_SAMPLE = {
  title: "My Quiz",
  description: "Short practice quiz",
  topic_tags: ["practice"],
  difficulty: 1,
  questions: [
    {
      id: "q1",
      prompt: "2 + 2 = ?",
      options: [
        { text: "3", correct: false },
        { text: "4", correct: true },
        { text: "5", correct: false },
      ],
      points: 10,
    },
  ],
};

export function CreatorPage() {
  const [games, setGames] = useState<Game[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [tags, setTags] = useState("ML");
  const [difficulty, setDifficulty] = useState(1);
  const [file, setFile] = useState<File | null>(null);

  const [templateType, setTemplateType] = useState("quiz");
  const [templateJson, setTemplateJson] = useState(JSON.stringify(QUIZ_SAMPLE, null, 2));

  const [aiTopic, setAiTopic] = useState("photosynthesis");
  const [aiType, setAiType] = useState("quiz");
  const [aiDiff, setAiDiff] = useState(2);
  const [aiCount, setAiCount] = useState(5);

  async function reload() {
    const list = await api<Game[]>("/api/games/mine");
    setGames(list);
  }

  useEffect(() => {
    reload().catch((err) => setError(err.message));
  }, []);

  async function upload(e: FormEvent) {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const form = new FormData();
      form.append("title", title);
      form.append("description", description);
      form.append("topic_tags", tags);
      form.append("difficulty", String(difficulty));
      form.append("file", file);
      await api<Game>("/api/games/upload", { method: "POST", body: form });
      setMessage("Upload complete — SDK metrics injected.");
      setTitle("");
      setFile(null);
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  async function createTemplate(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const content = JSON.parse(templateJson);
      await api<Game>("/api/games/from-template", {
        method: "POST",
        body: JSON.stringify({ template_type: templateType, content }),
      });
      setMessage("Template game created.");
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Template create failed");
    } finally {
      setBusy(false);
    }
  }

  async function generate(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await api<Game>("/api/games/generate", {
        method: "POST",
        body: JSON.stringify({
          topic: aiTopic,
          difficulty: aiDiff,
          template_type: aiType,
          question_count: aiCount,
        }),
      });
      setMessage("AI game generated.");
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "AI generate failed");
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    if (!confirm("Delete this game?")) return;
    await api(`/api/games/${id}`, { method: "DELETE" });
    await reload();
  }

  return (
    <div>
      <section className="hero">
        <h1>Creator studio</h1>
        <p>Upload HTML games, build from templates, or generate with AI. Tracking is added automatically.</p>
      </section>
      {error && <div className="error">{error}</div>}
      {message && <div className="panel" style={{ marginBottom: 12 }}>{message}</div>}

      <div className="panel" style={{ marginBottom: 16 }}>
        <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>Upload game</h2>
        <form className="form" onSubmit={upload}>
          <label>
            Title
            <input value={title} onChange={(e) => setTitle(e.target.value)} required />
          </label>
          <label>
            Description
            <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2} />
          </label>
          <label>
            Topic
            <select value={tags} onChange={(e) => setTags(e.target.value)}>
              <option value="ML">ML</option>
              <option value="Physics">Physics</option>
              <option value="Math">Math</option>
            </select>
          </label>
          <label>
            Level
            <input
              type="number"
              min={1}
              max={5}
              value={difficulty}
              onChange={(e) => setDifficulty(Number(e.target.value))}
            />
          </label>
          <label>
            HTML or ZIP file
            <input
              type="file"
              accept=".html,.htm,.zip"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              required
            />
          </label>
          <button className="btn accent" disabled={busy} type="submit">
            Upload
          </button>
        </form>
      </div>

      <div className="panel" style={{ marginBottom: 16 }}>
        <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>From template</h2>
        <form className="form" onSubmit={createTemplate} style={{ maxWidth: "100%" }}>
          <label>
            Template
            <select value={templateType} onChange={(e) => setTemplateType(e.target.value)}>
              <option value="quiz">quiz</option>
              <option value="drag_match">drag_match</option>
              <option value="timed_challenge">timed_challenge</option>
            </select>
          </label>
          <label>
            Content JSON
            <textarea
              value={templateJson}
              onChange={(e) => setTemplateJson(e.target.value)}
              rows={14}
              style={{ fontFamily: "ui-monospace, monospace", fontSize: 13 }}
            />
          </label>
          <button className="btn" disabled={busy} type="submit">
            Create from template
          </button>
        </form>
      </div>

      <div className="panel" style={{ marginBottom: 16 }}>
        <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>AI generate</h2>
        <form className="form" onSubmit={generate}>
          <label>
            Topic
            <input value={aiTopic} onChange={(e) => setAiTopic(e.target.value)} required />
          </label>
          <label>
            Template
            <select value={aiType} onChange={(e) => setAiType(e.target.value)}>
              <option value="quiz">quiz</option>
              <option value="drag_match">drag_match</option>
              <option value="timed_challenge">timed_challenge</option>
            </select>
          </label>
          <label>
            Difficulty
            <input type="number" min={1} max={5} value={aiDiff} onChange={(e) => setAiDiff(Number(e.target.value))} />
          </label>
          <label>
            Item count
            <input
              type="number"
              min={3}
              max={12}
              value={aiCount}
              onChange={(e) => setAiCount(Number(e.target.value))}
            />
          </label>
          <button className="btn accent" disabled={busy} type="submit">
            Generate with AI
          </button>
          <p className="meta">Requires OPENAI_API_KEY in the backend environment.</p>
        </form>
      </div>

      <div className="panel">
        <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>My games</h2>
        <table className="table">
          <thead>
            <tr>
              <th>Title</th>
              <th>Source</th>
              <th>Difficulty</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {games.map((g) => (
              <tr key={g.id}>
                <td>{g.title}</td>
                <td>{g.source}</td>
                <td>{g.difficulty}</td>
                <td className="row">
                  <Link className="btn secondary" to={`/play/${g.id}`}>
                    Play
                  </Link>
                  <button className="btn danger" type="button" onClick={() => remove(g.id)}>
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
