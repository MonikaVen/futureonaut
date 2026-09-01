import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, type Game, type Session } from "../api";
import { useAuth } from "../auth";
import { useLanguage } from "../language";

type SdkMessage = {
  source?: string;
  type?: string;
  payload?: Record<string, unknown>;
};

export function PlayPage() {
  const { gameId } = useParams();
  const { user } = useAuth();
  const { lang, t } = useLanguage();
  const [game, setGame] = useState<Game | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [points, setPoints] = useState(0);
  const [correct, setCorrect] = useState(0);
  const [attempts, setAttempts] = useState(0);
  const [timeMs, setTimeMs] = useState(0);
  const [error, setError] = useState("");
  const [frameReady, setFrameReady] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!gameId) return;
    let cancelled = false;
    setFrameReady(false);
    setReady(false);
    setSession(null);
    setPoints(0);
    setCorrect(0);
    setAttempts(0);
    setTimeMs(0);
    (async () => {
      try {
        const g = await api<Game>(`/api/games/${gameId}`);
        if (cancelled) return;
        setGame(g);
        api(`/api/games/${gameId}/view`, { method: "POST" }).catch(() => {});
        if (user) {
          const s = await api<Session>("/api/sessions", {
            method: "POST",
            body: JSON.stringify({ game_id: gameId }),
          });
          if (!cancelled) setSession(s);
        }
        if (!cancelled) setReady(true);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to start");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [gameId, user]);

  useEffect(() => {
    function onMessage(ev: MessageEvent<SdkMessage>) {
      const data = ev.data;
      if (!data || data.source !== "learnplay-sdk" || !data.type) return;
      const payload = data.payload || {};

      if (data.type === "score") setPoints((p) => p + Number(payload.delta || 0));
      if (data.type === "answer") {
        setAttempts((a) => a + 1);
        if (payload.correct) setCorrect((c) => c + 1);
      }
      if (data.type === "task_time" && payload.phase === "end") {
        setTimeMs((t) => t + Number(payload.durationMs || 0));
      }

      if (!session) return;
      api<Session>(`/api/sessions/${session.id}/events`, {
        method: "POST",
        body: JSON.stringify({ type: data.type, payload }),
      })
        .then((s) => {
          setSession(s);
          setPoints(s.total_points);
          setCorrect(s.correct_count);
          setAttempts(s.attempt_count);
          setTimeMs(s.total_time_ms);
        })
        .catch(() => {
          /* ignore transient */
        });
    }
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [session]);

  const src = useMemo(() => {
    if (!game) return "";
    const needsTranslate = (game.source_language || "en") !== lang;
    const q = needsTranslate ? `?lang=${encodeURIComponent(lang)}` : "";
    return `/api/games/${game.id}/files/${game.entry_path}${q}`;
  }, [game, lang]);

  if (error) {
    return (
      <div>
        <div className="error">{error}</div>
        <Link to="/">Back</Link>
      </div>
    );
  }

  if (!game || !ready) return <p className="meta">Starting…</p>;

  const translating = (game.source_language || "en") !== lang && !frameReady;

  return (
    <div className="player-wrap">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div>
          <h1 style={{ fontFamily: "var(--font-display)", margin: 0 }}>{game.title}</h1>
          <p className="meta">
            {game.description} · {t("detected")}: {(game.source_language || "en").toUpperCase()} →{" "}
            {lang.toUpperCase()}
          </p>
        </div>
        {user ? (
          <Link className="btn secondary" to="/dashboard">
            {t("dashboard")}
          </Link>
        ) : (
          <Link className="btn secondary" to="/login">
            {t("signInToTrack")}
          </Link>
        )}
      </div>
      {!user && <p className="guest-note">{t("guestPlayNote")}</p>}
      <div className="metrics">
        <span>
          Points <b>{points}</b>
        </span>
        <span>
          Correct <b>
            {correct}/{attempts}
          </b>
        </span>
        <span>
          Task time <b>{(timeMs / 1000).toFixed(1)}s</b>
        </span>
      </div>
      {translating && <p className="meta">{t("translating")}</p>}
      <iframe
        key={src}
        className="frame"
        title={game.title}
        src={src}
        sandbox="allow-scripts allow-same-origin allow-forms"
        onLoad={() => setFrameReady(true)}
      />
    </div>
  );
}
