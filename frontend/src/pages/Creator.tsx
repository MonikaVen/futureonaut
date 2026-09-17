import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Classroom, type Game, type GameAnalytics, type GameAnalyticsDetail, type GameDraft } from "../api";
import { CreatorDraftStudio } from "../CreatorDraftStudio";
import { GameAnalyticsDetailPanel } from "../GameAnalyticsDetail";
import { useAuth } from "../auth";
import { useLanguage } from "../language";

const LLM_KEY_STORAGE = "futureonaut_llm_api_key";

export function CreatorPage() {
  const { user, refreshMe } = useAuth();
  const { t } = useLanguage();
  const [games, setGames] = useState<Game[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [detailId, setDetailId] = useState<string | null>(null);
  const [detail, setDetail] = useState<GameAnalyticsDetail | null>(null);
  const [analytics, setAnalytics] = useState<GameAnalytics[]>([]);
  const [provider, setProvider] = useState(user?.llm_provider || "openai");
  const [apiKey, setApiKey] = useState(() => sessionStorage.getItem(LLM_KEY_STORAGE) || "");
  const [model, setModel] = useState("gpt-4o-mini");
  const [assignClassId, setAssignClassId] = useState("");
  const [classrooms, setClassrooms] = useState<Classroom[]>([]);
  const [draft, setDraft] = useState<GameDraft | null>(null);
  const [drafts, setDrafts] = useState<GameDraft[]>([]);

  async function reload(keepDraft = true) {
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
      if (!keepDraft) {
        setDraft(null);
        return;
      }
      setDraft((current) => {
        if (current) {
          const fresh = open.find((item) => item.id === current.id);
          if (fresh) return fresh;
        }
        return current ?? open[0] ?? null;
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

  async function sendChat(text: string) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const next = await api<GameDraft>("/api/games/drafts/chat", {
        method: "POST",
        body: JSON.stringify({
          message: text,
          draft_id: draft?.id || null,
          language: document.documentElement.lang || "en",
          provider,
          api_key: apiKey,
          model: model || undefined,
          assign_classroom_id: assignClassId || null,
        }),
      });
      setDraft(next);
      await refreshMe();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("reviseGame"));
    } finally {
      setBusy(false);
    }
  }

  async function deployDraft(title?: string) {
    if (!draft) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const game = await api<Game>(`/api/games/drafts/${draft.id}/publish`, {
        method: "POST",
        body: JSON.stringify({
          title: (title || draft.title).trim() || draft.title,
          assign_classroom_id: assignClassId || null,
        }),
      });
      const updated = Boolean(draft.source_game_id);
      setDraft(null);
      setMessage(`${updated ? t("gameUpdated") : t("gamePublished")} ${game.title}`);
      await reload(false);
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
      await reload(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("discardDraft"));
    } finally {
      setBusy(false);
    }
  }

  async function startEdit(id: string) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const next = await api<GameDraft>(`/api/games/${id}/edit-draft`, { method: "POST" });
      setDraft(next);
      document.querySelector(".draft-studio")?.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (err) {
      setError(err instanceof Error ? err.message : t("editGame"));
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
        <form className="form creator-llm-bar" onSubmit={(e) => e.preventDefault()}>
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
          <label>
            {t("modelOptional")}
            <input value={model} onChange={(e) => setModel(e.target.value)} placeholder="gpt-4o-mini" />
          </label>
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
        </form>
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

      <div className="panel" style={{ marginBottom: 16 }}>
        <CreatorDraftStudio
          draft={draft}
          apiKey={apiKey}
          busy={busy}
          onSend={sendChat}
          onDeploy={deployDraft}
          onDiscard={discardDraft}
          onNew={() => setDraft(null)}
        />
      </div>

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

      <div className="panel">
        <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>My games</h2>
        <table className="table">
          <thead>
            <tr>
              <th>{t("titleSort")}</th>
              <th>{t("gameHandle")}</th>
              <th>Source</th>
              <th>{t("level")}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {games.map((g) => (
              <tr key={g.id}>
                <td>{g.title}</td>
                <td>
                  <code className="game-handle">{g.handle || g.id.slice(0, 8)}</code>
                </td>
                <td>{g.source}</td>
                <td>{g.difficulty}</td>
                <td className="row">
                  <Link className="btn secondary" to={g.handle ? `/play/${g.handle}` : `/play/${g.id}`}>
                    {t("play")}
                  </Link>
                  <button className="btn secondary" type="button" disabled={busy} onClick={() => startEdit(g.id)}>
                    {t("editGame")}
                  </button>
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
