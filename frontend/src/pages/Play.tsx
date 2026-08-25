import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, type Game, type Session } from "../api";
import { useLanguage } from "../language";

type SdkMessage = {
  source?: string;
  type?: string;
  payload?: Record<string, unknown>;
};

export function PlayPage() {
  const { gameId } = useParams();
  const { lang, t } = useLanguage();
  const [game, setGame] = useState<Game | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [points, setPoints] = useState(0);
  const [correct, setCorrect] = useState(0);
  const [attempts, setAttempts] = useState(0);
  const [timeMs, setTimeMs] = useState(0);
  const [error, setError] = useState("");
  const [frameReady, setFrameReady] = useState(false);

  useEffect(() => {
    if (!gameId) return;
    let cancelled = false;
    setFrameReady(false);
    (async () => {
      try {
        const g = await api<Game>(`/api/games/${gameId}`);
        const s = await api<Session>("/api/sessions", {
          method: "POST",
          body: JSON.stringify({ game_id: gameId }),
        });
        if (!cancelled) {
          setGame(g);
          setSession(s);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to start");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [gameId]);

  useEffect(() => {
    if (!session) return;
    function onMessage(ev: MessageEvent<SdkMessage>) {
      const data = ev.data;
      if (!data || data.source !== "learnplay-sdk" || !data.type) return;
      const payload = data.payload || {};
      api<Session>(`/api/sessions/${session!.id}/events`, {
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

      if (data.type === "score") setPoints((p) => p + Number(payload.delta || 0));
      if (data.type === "answer") {
        setAttempts((a) => a + 1);
        if (payload.correct) setCorrect((c) => c + 1);
      }
      if (data.type === "task_time" && payload.phase === "end") {
        setTimeMs((t) => t + Number(payload.durationMs || 0));
      }
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

  if (!game || !session) return <p className="meta">Starting session…</p>;

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
        <Link className="btn secondary" to="/dashboard">
          {t("dashboard")}
        </Link>
      </div>
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
