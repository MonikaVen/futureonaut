import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Classroom, type CreatorStyle, type Game, type GameAnalytics, type GameAnalyticsDetail, type GameDraft } from "../api";
import { AvatarEditor } from "../AvatarEditor";
import { CreatorDraftStudio } from "../CreatorDraftStudio";
import { GameAnalyticsDetailPanel } from "../GameAnalyticsDetail";
import { useAuth } from "../auth";
import { useLanguage } from "../language";

const LLM_PROVIDERS = ["openai", "claude", "grok"] as const;

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
  const [keyDrafts, setKeyDrafts] = useState<Record<string, string>>({ openai: "", claude: "", grok: "" });
  const [model, setModel] = useState("gpt-4o-mini");
  const [assignClassId, setAssignClassId] = useState("");
  const [classrooms, setClassrooms] = useState<Classroom[]>([]);
  const [draft, setDraft] = useState<GameDraft | null>(null);
  const [drafts, setDrafts] = useState<GameDraft[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [shotBust, setShotBust] = useState<Record<string, number>>({});
  const [styleSource, setStyleSource] = useState<"futureonaut" | "custom">("futureonaut");
  const [customStyle, setCustomStyle] = useState("");
  const [defaultStyle, setDefaultStyle] = useState("");

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
      const prefs = await api<CreatorStyle>("/api/creator/style");
      setStyleSource(prefs.source === "custom" ? "custom" : "futureonaut");
      setCustomStyle(prefs.custom_guidelines || "");
      setDefaultStyle(prefs.default_guidelines || "");
    } catch {
      setDefaultStyle("");
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
    if (user?.llm_provider) setProvider(user.llm_provider);
  }, [user?.llm_provider]);

  function savedHint(name: string) {
    return user?.llm_keys?.find((item) => item.provider === name)?.hint || "";
  }

  function hasProviderKey(name: string) {
    return Boolean((keyDrafts[name] || "").trim() || savedHint(name) || (user?.llm_provider === name && user?.llm_key_configured));
  }

  async function saveKey(name: string) {
    const value = (keyDrafts[name] || "").trim();
    if (!value) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await api("/api/auth/llm-key", {
        method: "POST",
        body: JSON.stringify({ provider: name, api_key: value }),
      });
      setKeyDrafts((current) => ({ ...current, [name]: "" }));
      await refreshMe();
      setMessage(t("apiKeySaved"));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("saveApiKey"));
    } finally {
      setBusy(false);
    }
  }

  async function clearKey(name: string) {
    setBusy(true);
    setError("");
    try {
      await api(`/api/auth/llm-key?provider=${encodeURIComponent(name)}`, { method: "DELETE" });
      setKeyDrafts((current) => ({ ...current, [name]: "" }));
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
      const pasted = (keyDrafts[provider] || "").trim();
      const next = await api<GameDraft>("/api/games/drafts/chat", {
        method: "POST",
        body: JSON.stringify({
          message: text,
          draft_id: draft?.id || null,
          language: document.documentElement.lang || "en",
          provider,
          api_key: pasted || undefined,
          model: model || undefined,
          assign_classroom_id: assignClassId || null,
        }),
      });
      if (pasted) setKeyDrafts((current) => ({ ...current, [provider]: "" }));
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

  function startRename(game: Game) {
    setEditingId(game.id);
    setEditTitle(game.title);
  }

  async function setPublic(game: Game, isPublic: boolean) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await api(`/api/games/${game.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_public: isPublic }),
      });
      setMessage(isPublic ? t("gameNowPublic") : t("gameNowPrivate"));
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("makePrivate"));
    } finally {
      setBusy(false);
    }
  }

  async function saveTitle(game: Game) {
    const title = editTitle.trim();
    if (!title) {
      setError(t("titleRequired"));
      return;
    }
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await api(`/api/games/${game.id}`, {
        method: "PATCH",
        body: JSON.stringify({ title }),
      });
      setEditingId(null);
      setMessage(`${t("gameUpdated")} ${title}`);
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("renameGame"));
    } finally {
      setBusy(false);
    }
  }

  async function uploadSnapshot(game: Game, file: File) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const body = new FormData();
      body.append("icon", file);
      await api<Game>(`/api/games/${game.id}/snapshot`, { method: "POST", body });
      setShotBust((current) => ({ ...current, [game.id]: Date.now() }));
      setMessage(`${t("snapshotUpdated")} ${game.title}`);
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("updateSnapshot"));
    } finally {
      setBusy(false);
    }
  }

  async function saveStyle() {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const prefs = await api<CreatorStyle>("/api/creator/style", {
        method: "PUT",
        body: JSON.stringify({
          source: styleSource,
          custom_guidelines: customStyle,
        }),
      });
      setStyleSource(prefs.source === "custom" ? "custom" : "futureonaut");
      setCustomStyle(prefs.custom_guidelines || "");
      setDefaultStyle(prefs.default_guidelines || "");
      setMessage(t("styleSaved"));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("saveStyle"));
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
        <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>{t("yourAvatar")}</h2>
        <AvatarEditor compact />
        {user?.slug ? (
          <p className="meta">
            <Link to={`/u/${user.slug}`}>{t("viewCreatorPage")}</Link>
          </p>
        ) : null}
      </div>

      <div className="panel" style={{ marginBottom: 16 }}>
        <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>{t("llmKeys")}</h2>
        <p className="meta">{t("llmKeysHelp")}</p>
        <div className="llm-key-list">
          {LLM_PROVIDERS.map((name) => {
            const hint = savedHint(name);
            return (
              <div key={name} className="llm-key-row">
                <strong>{t(name)}</strong>
                <span className="meta">
                  {hint ? `${t("apiKeySaved")} ••••${hint}` : t("apiKeyMissing")}
                </span>
                <input
                  type="password"
                  autoComplete="off"
                  value={keyDrafts[name] || ""}
                  onChange={(e) => setKeyDrafts((current) => ({ ...current, [name]: e.target.value }))}
                  placeholder={hint ? t("replaceApiKey") : t("apiKey")}
                />
                <button
                  className="btn secondary btn-sm"
                  type="button"
                  disabled={busy || !(keyDrafts[name] || "").trim()}
                  onClick={() => void saveKey(name)}
                >
                  {t("saveApiKey")}
                </button>
                {hint ? (
                  <button className="btn secondary btn-sm" type="button" disabled={busy} onClick={() => void clearKey(name)}>
                    {t("clearApiKey")}
                  </button>
                ) : null}
              </div>
            );
          })}
        </div>
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
          {hasProviderKey(provider) ? t("usingSavedKey") : t("pasteApiKeyToSend")}
        </p>
      </div>

      <div className="panel" style={{ marginBottom: 16 }}>
        <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>{t("styleGuidelines")}</h2>
        <p className="meta">{t("styleGuidelinesHelp")}</p>
        <div className="style-choice" role="radiogroup" aria-label={t("styleGuidelines")}>
          <label className={`style-choice-card${styleSource === "futureonaut" ? " is-selected" : ""}`}>
            <input
              type="radio"
              name="style-source"
              checked={styleSource === "futureonaut"}
              onChange={() => setStyleSource("futureonaut")}
            />
            <span>
              <strong>{t("futureonautStyle")}</strong>
              <span className="meta">{t("futureonautStyleHelp")}</span>
            </span>
          </label>
          <label className={`style-choice-card${styleSource === "custom" ? " is-selected" : ""}`}>
            <input
              type="radio"
              name="style-source"
              checked={styleSource === "custom"}
              onChange={() => setStyleSource("custom")}
            />
            <span>
              <strong>{t("customStyle")}</strong>
              <span className="meta">{t("customStyleHelp")}</span>
            </span>
          </label>
        </div>
        {styleSource === "futureonaut" ? (
          <pre className="style-preview">{defaultStyle || t("styleLoading")}</pre>
        ) : (
          <label>
            {t("customStyle")}
            <textarea
              rows={8}
              value={customStyle}
              onChange={(e) => setCustomStyle(e.target.value)}
              placeholder={t("customStylePlaceholder")}
            />
          </label>
        )}
        <div className="form-actions">
          <button className="btn accent" type="button" disabled={busy} onClick={saveStyle}>
            {t("saveStyle")}
          </button>
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
          apiKey={hasProviderKey(provider) ? "saved" : ""}
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
        <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>{t("myGames")}</h2>
        <p className="meta">{t("snapshotHelp")}</p>
        <table className="table">
          <thead>
            <tr>
              <th>{t("titleSort")}</th>
              <th>{t("gameHandle")}</th>
              <th>{t("updateSnapshot")}</th>
              <th>{t("level")}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {games.map((g) => (
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
                        aria-label={t("titleSort")}
                      />
                      <button className="btn accent btn-sm" type="submit" disabled={busy}>
                        {t("saveTitle")}
                      </button>
                      <button
                        className="btn secondary btn-sm"
                        type="button"
                        onClick={() => setEditingId(null)}
                      >
                        {t("cancelEdit")}
                      </button>
                    </form>
                  ) : (
                    <div className="creator-title-cell">
                      <span>{g.title}</span>
                      {g.is_public === false ? <span className="tag private">{t("privateGame")}</span> : null}
                      <button className="btn secondary btn-sm" type="button" disabled={busy} onClick={() => startRename(g)}>
                        {t("renameGame")}
                      </button>
                    </div>
                  )}
                </td>
                <td>
                  <code className="game-handle">{g.handle || g.id.slice(0, 8)}</code>
                </td>
                <td>
                  <div className="creator-shot-actions">
                    {g.has_screenshot ? (
                      <img
                        className="creator-shot"
                        src={`/share/${g.id}/shot.png?v=${shotBust[g.id] || 1}`}
                        alt=""
                      />
                    ) : null}
                    <input
                      id={`shot-${g.id}`}
                      className="sr-only"
                      type="file"
                      accept="image/png,image/jpeg,image/webp,image/gif"
                      disabled={busy}
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        e.target.value = "";
                        if (file) void uploadSnapshot(g, file);
                      }}
                    />
                    <label className="btn secondary btn-sm" htmlFor={`shot-${g.id}`}>
                      {t("updateSnapshot")}
                    </label>
                  </div>
                </td>
                <td>{g.difficulty}</td>
                <td className="row">
                  <Link className="btn secondary" to={g.handle ? `/play/${g.handle}` : `/play/${g.id}`}>
                    {t("play")}
                  </Link>
                  <button className="btn secondary" type="button" disabled={busy} onClick={() => startEdit(g.id)}>
                    {t("editGame")}
                  </button>
                  {user?.role === "admin" || user?.role === "creator" ? (
                    <button
                      className="btn secondary"
                      type="button"
                      disabled={busy}
                      onClick={() => void setPublic(g, g.is_public === false)}
                    >
                      {g.is_public === false ? t("makePublic") : t("makePrivate")}
                    </button>
                  ) : null}
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
