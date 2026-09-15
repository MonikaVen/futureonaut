import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, type Game, type Session } from "../api";
import { useAuth } from "../auth";
import { GameShare } from "../GameShare";
import { GameSocial } from "../GameSocial";
import { ScoreCard } from "../ScoreCard";
import { useLanguage } from "../language";
import { getVisitorId } from "../visitor";

type SdkMessage = {
  source?: string;
  type?: string;
  payload?: Record<string, unknown>;
};

export function PlayPage() {
  const { gameId } = useParams();
  const { user } = useAuth();
  const { t } = useLanguage();
  const visitorId = useMemo(() => getVisitorId(), []);
  const [game, setGame] = useState<Game | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [points, setPoints] = useState(0);
  const [correct, setCorrect] = useState(0);
  const [attempts, setAttempts] = useState(0);
  const [timeMs, setTimeMs] = useState(0);
  const [completed, setCompleted] = useState(false);
  const [levelsCompleted, setLevelsCompleted] = useState(0);
  const [totalLevels, setTotalLevels] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [ready, setReady] = useState(false);
  const frameRef = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    if (!gameId) return;
    let cancelled = false;
    setReady(false);
    setSession(null);
    setPoints(0);
    setCorrect(0);
    setAttempts(0);
    setTimeMs(0);
    setCompleted(false);
    setLevelsCompleted(0);
    setTotalLevels(null);
    (async () => {
      try {
        const g = await api<Game>(`/api/games/${gameId}`);
        if (cancelled) return;
        setGame(g);
        api(`/api/games/${gameId}/view`, { method: "POST", visitorId }).catch(() => {});
        const s = user
          ? await api<Session>("/api/sessions", {
              method: "POST",
              body: JSON.stringify({ game_id: gameId }),
            })
          : await api<Session>("/api/sessions/guest", {
              method: "POST",
              body: JSON.stringify({ game_id: gameId, visitor_id: visitorId }),
            });
        if (!cancelled) {
          setSession(s);
          setPoints(s.total_points);
          setCorrect(s.correct_count);
          setAttempts(s.attempt_count);
          setTimeMs(s.total_time_ms);
          setLevelsCompleted(s.levels_completed ?? 0);
          setTotalLevels(s.total_levels ?? null);
          setCompleted(Boolean(s.ended_at));
          setReady(true);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to start");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [gameId, user, visitorId]);

  useEffect(() => {
    function onMessage(ev: MessageEvent<SdkMessage>) {
      if (ev.source !== frameRef.current?.contentWindow) return;
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
        visitorId: user ? undefined : visitorId,
      })
        .then((s) => {
          setSession(s);
          setPoints(s.total_points);
          setCorrect(s.correct_count);
          setAttempts(s.attempt_count);
          setTimeMs(s.total_time_ms);
          setLevelsCompleted(s.levels_completed ?? 0);
          setTotalLevels(s.total_levels ?? null);
          if (data.type === "complete" || data.type === "level_complete" || data.type === "milestone" || s.ended_at) {
            setCompleted(Boolean(s.ended_at) || (
              (s.total_levels ?? 0) > 0 && (s.levels_completed ?? 0) >= (s.total_levels ?? 0)
            ));
          }
        })
        .catch(() => {
          /* ignore transient */
        });
    }
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [session, user, visitorId]);

  const src = game ? `/api/games/${game.id}/files/${game.entry_path}` : "";

  if (error) {
    return (
      <div>
        <div className="error">{error}</div>
        <Link to="/">{t("back")}</Link>
      </div>
    );
  }

  if (!game || !ready) return <p className="meta">{t("starting")}</p>;

  return (
    <div className="player-wrap">
      <div className="player-bar">
        <Link className="player-back" to="/">
          {t("back")}
        </Link>
        <h1 className="player-title">{game.title}</h1>
        <div className="metrics metrics-inline" aria-live="polite">
          <span>
            {t("points")} <b>{points}</b>
          </span>
          <span>
            {t("correct")}{" "}
            <b>
              {correct}/{attempts}
            </b>
          </span>
          <span>
            {t("taskTime")} <b>{(timeMs / 1000).toFixed(1)}s</b>
          </span>
          {totalLevels || levelsCompleted ? (
            <span>
              {t("level")}{" "}
              <b>
                {levelsCompleted}
                {totalLevels ? `/${totalLevels}` : ""}
              </b>
            </span>
          ) : null}
        </div>
      </div>
      {!user && <p className="guest-note">{t("guestPlayNote")}</p>}
      <iframe
        ref={frameRef}
        className="frame"
        title={game.title}
        src={src}
        sandbox="allow-scripts allow-forms"
        referrerPolicy="no-referrer"
      />
      {completed && session && (
        <div className="player-after">
          <ScoreCard
            sessionId={session.id}
            gameTitle={game.title}
            points={session.total_points}
            correct={session.correct_count}
            attempts={session.attempt_count}
            levelsCompleted={session.levels_completed}
            totalLevels={session.total_levels}
          />
          <div className="row player-tools">
            <GameSocial
              game={{
                ...game,
                like_count: game.like_count ?? 0,
                comment_count: game.comment_count ?? 0,
                liked_by_me: game.liked_by_me ?? false,
              }}
              showComments
              onUpdate={(patch) => setGame((g) => (g ? { ...g, ...patch } : g))}
            />
            <GameShare gameId={game.id} title={game.title} description={game.description} />
          </div>
        </div>
      )}
    </div>
  );
}
