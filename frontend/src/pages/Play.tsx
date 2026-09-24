import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, getAccessToken, type ClassroomDetail, type Game, type Session } from "../api";
import { useAuth } from "../auth";
import { GameShare } from "../GameShare";
import { GameSocial } from "../GameSocial";
import { ScoreCard } from "../ScoreCard";
import { UI_LANGS, useLanguage, type LangCode } from "../language";
import { useTheme, type Theme } from "../theme";
import { getVisitorId } from "../visitor";
import { GameFrame } from "../GameFrame";
import { classIssueNote } from "../grammarGrove";

type SdkMessage = {
  source?: string;
  type?: string;
  payload?: Record<string, unknown>;
};

export function PlayPage() {
  const { gameId, ownerSlug, gameSlug } = useParams();
  const [searchParams] = useSearchParams();
  const classId = searchParams.get("class");
  const playRef = ownerSlug && gameSlug ? `${ownerSlug}/${gameSlug}` : gameId;
  const navigate = useNavigate();
  const { user } = useAuth();
  const { t, lang, setLang } = useLanguage();
  const { theme: platformTheme } = useTheme();
  const visitorId = useMemo(() => getVisitorId(), []);
  const [game, setGame] = useState<Game | null>(null);
  const [gameTheme, setGameTheme] = useState<Theme>(platformTheme);
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
  const [frameHeight, setFrameHeight] = useState<number | null>(null);
  const [classConfig, setClassConfig] = useState<string | null>(classId ? null : "");
  const [className, setClassName] = useState("");
  const frameRef = useRef<HTMLIFrameElement>(null);
  const iframeSrcRef = useRef("");
  const iframeGameIdRef = useRef<string | null>(null);
  const loadedUserRef = useRef<string>("");
  const gameRef = useRef(game);
  gameRef.current = game;
  const prefsRef = useRef({ theme: gameTheme, lang });
  prefsRef.current = { theme: gameTheme, lang };
  const classConfigRef = useRef(classConfig);
  classConfigRef.current = classConfig;

  const postPrefs = useCallback((target?: Window | MessageEventSource | null) => {
    const win = (target && "postMessage" in target ? target : frameRef.current?.contentWindow) as
      | Window
      | null
      | undefined;
    if (!win || typeof win.postMessage !== "function") return;
    win.postMessage(
      { source: "learnplay-host", type: "prefs", payload: { ...prefsRef.current } },
      "*"
    );
  }, []);

  const postClassConfig = useCallback((target?: Window | MessageEventSource | null) => {
    const win = (target && "postMessage" in target ? target : frameRef.current?.contentWindow) as
      | Window
      | null
      | undefined;
    if (!win || typeof win.postMessage !== "function" || classConfigRef.current == null) return;
    win.postMessage(
      { source: "learnplay-host", type: "config", payload: { config: classConfigRef.current } },
      "*"
    );
  }, []);

  useEffect(() => {
    if (!playRef) return;
    const userKey = user?.id || "guest";
    const current = gameRef.current;
    if (current && (current.handle === playRef || current.id === playRef) && loadedUserRef.current === userKey) {
      return;
    }
    let cancelled = false;
    iframeSrcRef.current = "";
    iframeGameIdRef.current = null;
    setGameTheme(platformTheme);
    setReady(false);
    setSession(null);
    setPoints(0);
    setCorrect(0);
    setAttempts(0);
    setTimeMs(0);
    setCompleted(false);
    setLevelsCompleted(0);
    setTotalLevels(null);
    setFrameHeight(null);
    (async () => {
      try {
        const path = playRef.includes("/") ? `/api/games/by/${playRef}` : `/api/games/${playRef}`;
        const g = await api<Game>(path);
        if (cancelled) return;
        setGame(g);
        loadedUserRef.current = userKey;
        api(`/api/games/${g.id}/view`, { method: "POST", visitorId }).catch(() => {});
        const s = user
          ? await api<Session>("/api/sessions", {
              method: "POST",
              body: JSON.stringify({ game_id: g.id }),
            })
          : await api<Session>("/api/sessions/guest", {
              method: "POST",
              body: JSON.stringify({ game_id: g.id, visitor_id: visitorId }),
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
  }, [playRef, user, visitorId, navigate]);

  useEffect(() => {
    if (ready && game?.handle && playRef && game.handle !== playRef) {
      navigate(`/play/${game.handle}`, { replace: true });
    }
  }, [ready, game, playRef, navigate]);

  useEffect(() => {
    function onMessage(ev: MessageEvent<SdkMessage>) {
      if (ev.source !== frameRef.current?.contentWindow) return;
      const data = ev.data;
      if (!data || data.source !== "learnplay-sdk" || !data.type) return;
      const payload = data.payload || {};

      if (data.type === "resize") {
        const height = Number(payload.height);
        if (!Number.isFinite(height) || height <= 0) return;
        const reported = Math.ceil(height);
        const current = frameRef.current?.clientHeight ?? 0;
        // A game that fills the frame reports its own height. Growing the frame
        // makes the next report taller, so the page slides down without stopping.
        if (current > 0 && reported <= current + 80) return;
        setFrameHeight(Math.min(16000, Math.max(current || 420, reported)));
        return;
      }

      if (data.type === "ready") {
        postPrefs(ev.source as Window);
        return;
      }

      if (data.type === "prefs") {
        const nextTheme = payload.theme;
        const nextLang = typeof payload.lang === "string" ? payload.lang.slice(0, 2).toLowerCase() : "";
        if (nextTheme === "dark" || nextTheme === "light") {
          setGameTheme(nextTheme as Theme);
        }
        if (UI_LANGS.some((item) => item.code === nextLang)) {
          setLang(nextLang as LangCode);
        }
        return;
      }

      if (data.type === "score") setPoints((p) => p + Number(payload.delta || 0));
      if (data.type === "answer") {
        setAttempts((a) => a + 1);
        if (payload.correct) setCorrect((c) => c + 1);
      }
      if (data.type === "task_time" && payload.phase === "end") {
        setTimeMs((t) => t + Number(payload.durationMs || 0));
      }

      if (!session) return;
      if (
        data.type !== "score" &&
        data.type !== "answer" &&
        data.type !== "task_time" &&
        data.type !== "level_complete" &&
        data.type !== "milestone" &&
        data.type !== "complete"
      ) {
        return;
      }
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
  }, [session, user, visitorId, postPrefs, setLang]);

  useEffect(() => {
    postPrefs();
  }, [gameTheme, lang, ready, postPrefs]);

  useEffect(() => {
    if (!classId || !user) {
      setClassConfig("");
      setClassName("");
      return;
    }
    if (!game?.id) return;
    let cancelled = false;
    setClassConfig(null);
    api<ClassroomDetail>(`/api/classrooms/${classId}`)
      .then((detail) => {
        if (cancelled) return;
        const assignment = detail.assignments.find((item) => item.game_id === game.id);
        setClassName(detail.name);
        setClassConfig(assignment?.config || "");
      })
      .catch(() => {
        if (!cancelled) {
          setClassName("");
          setClassConfig("");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [classId, game?.id, user]);

  useEffect(() => {
    if (classConfig == null) return;
    postClassConfig();
  }, [classConfig, postClassConfig]);

  const src = useMemo(() => {
    if (!game || classConfig === null) return "";
    if (iframeGameIdRef.current === game.id && iframeSrcRef.current) {
      return iframeSrcRef.current;
    }
    const params = new URLSearchParams({ theme: gameTheme, lang });
    if (classConfig) params.set("lp_config", classConfig);
    const token = getAccessToken();
    if (token) params.set("access_token", token);
    const next = `/api/games/${game.id}/files/${game.entry_path}?${params.toString()}`;
    iframeGameIdRef.current = game.id;
    iframeSrcRef.current = next;
    return next;
  }, [game, gameTheme, lang, classConfig]);

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
        {game.owner_slug ? (
          <Link className="player-handle" to={`/u/${game.owner_slug}`}>
            {game.owner_name || game.owner_slug}
          </Link>
        ) : game.handle ? (
          <span className="player-handle">{game.handle}</span>
        ) : null}
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
      <div className="row player-tools">
        <GameSocial
          game={{
            ...game,
            like_count: game.like_count ?? 0,
            comment_count: game.comment_count ?? 0,
            liked_by_me: game.liked_by_me ?? false,
          }}
          onUpdate={(patch) => setGame((g) => (g ? { ...g, ...patch } : g))}
          showComments
        />
        <GameShare gameId={game.id} title={game.title} description={game.description} />
      </div>
      {classId && classConfig ? (
        <div className="panel class-issue" style={{ marginBottom: 12 }}>
          <h3 style={{ marginTop: 0 }}>{className ? `${className} issue` : "Class issue"}</h3>
          <p className="class-issue-note">{classIssueNote(classConfig)}</p>
        </div>
      ) : null}
      {src ? (
        <GameFrame
          ref={frameRef}
          className="frame"
          title={game.title}
          src={src}
          onLoad={() => {
            postPrefs();
            postClassConfig();
          }}
          style={frameHeight ? { height: frameHeight, minHeight: frameHeight } : undefined}
        />
      ) : (
        <p className="meta">Loading class issue…</p>
      )}
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
        </div>
      )}
    </div>
  );
}
