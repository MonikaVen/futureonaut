import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Classroom, type Game, type GameAnalytics, type GameAnalyticsDetail, type GameDraft } from "../api";
import { CreatorDraftStudio } from "../CreatorDraftStudio";
import { GameAnalyticsDetailPanel } from "../GameAnalyticsDetail";
import { useAuth } from "../auth";
import { useLanguage } from "../language";

const LLM_KEY_STORAGE = "futureonaut_llm_api_key";

const QUIZ_SAMPLE = {
  title: "My Quiz",
  description: "Short practice quiz",
  topic_tags: ["Math"],
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

const DRAG_SAMPLE = {
  title: "Match the terms",
  description: "Drag each term to its meaning",
  topic_tags: ["AI"],
  difficulty: 1,
  pairs: [
    { id: "p1", left: "Neuron", right: "A unit that transforms inputs into an output", points: 10 },
    { id: "p2", left: "Loss", right: "A number that measures prediction error", points: 10 },
  ],
};

const TIMED_SAMPLE = {
  title: "Quick recall",
  description: "Answer before the timer runs out",
  topic_tags: ["Physics"],
  difficulty: 1,
  items: [
    { id: "t1", prompt: "Unit of force?", answer: "newton", points: 10, time_limit_ms: 20000 },
    { id: "t2", prompt: "Speed of light symbol?", answer: "c", points: 10, time_limit_ms: 15000 },
  ],
};

const TEMPLATE_SAMPLES: Record<string, object> = {
  quiz: QUIZ_SAMPLE,
  drag_match: DRAG_SAMPLE,
  timed_challenge: TIMED_SAMPLE,
};

export function CreatorPage() {
  const { user, refreshMe } = useAuth();
  const { t } = useLanguage();
  const [games, setGames] = useState<Game[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [tags, setTags] = useState("ML");
  const [difficulty, setDifficulty] = useState(1);
  const [file, setFile] = useState<File | null>(null);
  const [icon, setIcon] = useState<File | null>(null);

  const [templateType, setTemplateType] = useState("quiz");
  const [templateJson, setTemplateJson] = useState(JSON.stringify(QUIZ_SAMPLE, null, 2));
  const [detailId, setDetailId] = useState<string | null>(null);
  const [detail, setDetail] = useState<GameAnalyticsDetail | null>(null);

  const [aiTopic, setAiTopic] = useState("photosynthesis");
  const [aiType, setAiType] = useState("quiz");
  const [aiDiff, setAiDiff] = useState(2);
  const [aiCount, setAiCount] = useState(5);
  const [analytics, setAnalytics] = useState<GameAnalytics[]>([]);

  const [provider, setProvider] = useState(user?.llm_provider || "openai");
  const [apiKey, setApiKey] = useState(() => sessionStorage.getItem(LLM_KEY_STORAGE) || "");
  const [model, setModel] = useState("");
  const [genTitle, setGenTitle] = useState("");
  const [genTopic, setGenTopic] = useState("neural networks");
  const [genDiff, setGenDiff] = useState(2);
  const [levelCount, setLevelCount] = useState(4);
  const [levelsBrief, setLevelsBrief] = useState(
    "Level 1: warm-up identifying the idea.\nLevel 2: practice with feedback.\nLevel 3: apply it in a short challenge.\nLevel 4: boss check that uses everything."
  );
  const [assignClassId, setAssignClassId] = useState("");
  const [classrooms, setClassrooms] = useState<Classroom[]>([]);
  const [draft, setDraft] = useState<GameDraft | null>(null);
  const [drafts, setDrafts] = useState<GameDraft[]>([]);

  async function reload() {
    const list = await api<Game[]>("/api/games/mine");
    setGames(list);
    try {
      const stats = await api<GameAnalytics[]>("/api/creator/analytics");
      setAnalytics(stats);
    } catch {
      setAnalytics([]);
    }
    try {
      const mine = await api<Classroom[]>("/api/classrooms/mine");
      setClassrooms(mine.filter((c) => c.teacher_id === user?.id));
    } catch {
      setClassrooms([]);
    }
    try {
      const open = await api<GameDraft[]>("/api/games/drafts");
      setDrafts(open);
      setDraft((current) => {
        if (current) {
          const fresh = open.find((item) => item.id === current.id);
          if (fresh) return fresh;
        }
        return open[0] || null;
      });
    } catch {
      setDrafts([]);
    }
  }

  useEffect(() => {
    reload().catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    if (apiKey) sessionStorage.setItem(LLM_KEY_STORAGE, apiKey);
    else sessionStorage.removeItem(LLM_KEY_STORAGE);
  }, [apiKey]);

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
      if (icon) form.append("icon", icon);
      await api<Game>("/api/games/upload", { method: "POST", body: form });
      setMessage("Upload complete — SDK metrics injected.");
      setTitle("");
      setFile(null);
      setIcon(null);
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
          provider,
          api_key: apiKey || undefined,
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

  async function saveKey() {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await api("/api/auth/llm-key", {
        method: "POST",
        body: JSON.stringify({ provider, api_key: apiKey }),
      });
      await refreshMe();
      setMessage(t("apiKeySaved"));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("saveApiKey"));
    } finally {
      setBusy(false);
    }
  }

  async function clearKey() {
    setBusy(true);
    setError("");
    try {
      await api("/api/auth/llm-key", { method: "DELETE" });
      setApiKey("");
      await refreshMe();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("clearApiKey"));
    } finally {
      setBusy(false);
    }
  }

  async function generateHtml(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const next = await api<GameDraft>("/api/games/generate-html", {
        method: "POST",
        body: JSON.stringify({
          title: genTitle,
          topic: genTopic,
          difficulty: genDiff,
          level_count: levelCount,
          levels_brief: levelsBrief,
          language: document.documentElement.lang || "en",
          provider,
          api_key: apiKey,
          model: model || undefined,
          assign_classroom_id: assignClassId || null,
        }),
      });
      setDraft(next);
      setMessage(t("gameDraftReady"));
      await refreshMe();
      await reload();
      setDraft(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("generateAndDeploy"));
    } finally {
      setBusy(false);
    }
  }

  async function reviseDraft(message: string) {
    if (!draft) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const next = await api<GameDraft>(`/api/games/drafts/${draft.id}/revise`, {
        method: "POST",
        body: JSON.stringify({
          message,
          provider,
          api_key: apiKey,
          model: model || undefined,
        }),
      });
      setDraft(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("reviseGame"));
    } finally {
      setBusy(false);
    }
  }

  async function publishDraft() {
    if (!draft) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const game = await api<Game>(`/api/games/drafts/${draft.id}/publish`, {
        method: "POST",
        body: JSON.stringify({
          title: genTitle || draft.title,
          assign_classroom_id: assignClassId || null,
        }),
      });
      setDraft(null);
      setMessage(`${t("gamePublished")} ${game.title}`);
      await reload();
      setDraft(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("publishGame"));
    } finally {
      setBusy(false);
    }
  }

  async function discardDraft() {
    if (!draft) return;
    if (!confirm(t("discardDraft"))) return;
    setBusy(true);
    setError("");
    try {
      await api(`/api/games/drafts/${draft.id}`, { method: "DELETE" });
      setDraft(null);
      await reload();
      setDraft(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("discardDraft"));
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
        <h1>{t("generateGame")}</h1>
        <p>{t("generateGameLede")}</p>
      </section>
      {error && <div className="error">{error}</div>}
      {message && <div className="panel" style={{ marginBottom: 12 }}>{message}</div>}

      <div className="panel" style={{ marginBottom: 16 }}>
        <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>{t("generateGame")}</h2>
        <form className="form" onSubmit={generateHtml} style={{ maxWidth: "100%" }}>
          <label>
            {t("llmProvider")}
            <select value={provider} onChange={(e) => setProvider(e.target.value)}>
              <option value="openai">{t("openai")}</option>
              <option value="claude">{t("claude")}</option>
              <option value="grok">{t("grok")}</option>
            </select>
          </label>
          <label>
            {t("apiKey")}
            <input
              type="password"
              autoComplete="off"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              required
            />
          </label>
          <p className="meta">
            {t("apiKeyHelp")}
            {user?.llm_key_configured ? ` ${t("apiKeySaved")}${user.llm_key_hint ? ` ••••${user.llm_key_hint}` : ""}.` : ""}
          </p>
          <div className="form-actions">
            <button className="btn secondary" type="button" disabled={busy || !apiKey} onClick={saveKey}>
              {t("saveApiKey")}
            </button>
            {user?.llm_key_configured ? (
              <button className="btn secondary" type="button" disabled={busy} onClick={clearKey}>
                {t("clearApiKey")}
              </button>
            ) : null}
          </div>
          <label>
            {t("modelOptional")}
            <input value={model} onChange={(e) => setModel(e.target.value)} placeholder="gpt-4o-mini" />
          </label>
          <label>
            Title
            <input value={genTitle} onChange={(e) => setGenTitle(e.target.value)} placeholder={genTopic} />
          </label>
          <label>
            Topic
            <input value={genTopic} onChange={(e) => setGenTopic(e.target.value)} required />
          </label>
          <label>
            Difficulty
            <input
              type="number"
              min={1}
              max={5}
              value={genDiff}
              onChange={(e) => setGenDiff(Number(e.target.value))}
            />
          </label>
          <label>
            {t("levelCount")}
            <input
              type="number"
              min={2}
              max={12}
              value={levelCount}
              onChange={(e) => setLevelCount(Number(e.target.value))}
            />
          </label>
          <label>
            {t("levelsBrief")}
            <textarea
              value={levelsBrief}
              onChange={(e) => setLevelsBrief(e.target.value)}
              rows={6}
              required
            />
          </label>
          <p className="meta">{t("levelsBriefHint")}</p>
          {classrooms.length > 0 && (
            <label>
              {t("assignToClass")}
              <select value={assignClassId} onChange={(e) => setAssignClassId(e.target.value)}>
                <option value="">{t("none")}</option>
                {classrooms.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>
          )}
          <button className="btn accent" disabled={busy} type="submit">
            {busy && !draft ? t("generatingGame") : t("generateAndDeploy")}
          </button>
        </form>
      </div>

      {drafts.length > 1 && (
        <div className="panel" style={{ marginBottom: 16 }}>
          <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>{t("openDraft")}</h2>
          <div className="row" style={{ flexWrap: "wrap", gap: 8 }}>
            {drafts.map((item) => (
              <button
                key={item.id}
                className={`btn ${draft?.id === item.id ? "accent" : "secondary"}`}
                type="button"
                onClick={() => setDraft(item)}
              >
                {item.title}
              </button>
            ))}
          </div>
        </div>
      )}

      {draft && (
        <div className="panel" style={{ marginBottom: 16 }}>
          <CreatorDraftStudio
            draft={draft}
            apiKey={apiKey}
            busy={busy}
            onRevise={reviseDraft}
            onPublish={publishDraft}
            onDiscard={discardDraft}
          />
        </div>
      )}

      {analytics.length > 0 && (
        <div className="panel" style={{ marginBottom: 16 }}>
          <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>Creator analytics</h2>
          <p className="meta">Click a game for funnel, task time, and recent sessions.</p>
          <table className="table">
            <thead>
              <tr>
                <th>Game</th>
                <th>Views</th>
                <th>Plays</th>
                <th>Players</th>
                <th>Avg time</th>
                <th>Avg levels</th>
                <th>Completion</th>
              </tr>
            </thead>
            <tbody>
              {analytics.map((row) => (
                <tr
                  key={row.game_id}
                  className={detailId === row.game_id ? "row-selected" : ""}
                  onClick={() => {
                    setDetailId(row.game_id);
                    api<GameAnalyticsDetail>(`/api/creator/analytics/${row.game_id}`)
                      .then(setDetail)
                      .catch((err) => setError(err.message));
                  }}
                  style={{ cursor: "pointer" }}
                >
                  <td>{row.title}</td>
                  <td>{row.views}</td>
                  <td>{row.plays}</td>
                  <td>{row.unique_players}</td>
                  <td>{(row.avg_time_ms / 1000).toFixed(1)}s</td>
                  <td>{row.avg_levels_completed.toFixed(1)}</td>
                  <td>{(row.completion_rate * 100).toFixed(0)}%</td>
                </tr>
              ))}
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
      )}

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
          <label>
            Screenshot (optional)
            <input
              type="file"
              accept="image/png,image/jpeg,image/webp,image/gif,.png,.jpg,.jpeg,.webp,.gif"
              onChange={(e) => setIcon(e.target.files?.[0] || null)}
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
            <select
              value={templateType}
              onChange={(e) => {
                const next = e.target.value;
                setTemplateType(next);
                const sample = TEMPLATE_SAMPLES[next];
                if (sample) setTemplateJson(JSON.stringify(sample, null, 2));
              }}
            >
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
          <p className="meta">{t("apiKeyHelp")}</p>
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
