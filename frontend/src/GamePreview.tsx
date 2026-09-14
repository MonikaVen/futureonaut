import type { CSSProperties } from "react";
import { Link } from "react-router-dom";
import { PlayIcon } from "./Icons";
import { posterKind } from "./gameMeta";
import { useLanguage } from "./language";

type Props = {
  gameId: string;
  title: string;
  description?: string;
  topic: string;
  difficulty: number;
  progressLabel?: string;
  progressPct?: number | null;
};

function orbStyle(id: string): CSSProperties {
  let n = 0;
  for (let i = 0; i < id.length; i += 1) {
    n = (n * 33 + id.charCodeAt(i)) >>> 0;
  }
  return {
    "--orb-x": `${12 + (n % 76)}%`,
    "--orb-y": `${(n >> 8) % 48}%`,
  } as CSSProperties;
}

export function GamePreview({
  gameId,
  title,
  description,
  topic,
  difficulty,
  progressLabel,
  progressPct,
}: Props) {
  const { t } = useLanguage();
  const kind = posterKind(topic);
  const lede = description?.trim();
  const clampedPct =
    typeof progressPct === "number" ? Math.max(0, Math.min(100, progressPct)) : null;

  return (
    <Link
      className={`game-preview topic-${kind}`}
      to={`/play/${gameId}`}
      aria-label={`${t("play")} ${title}`}
      style={orbStyle(gameId)}
    >
      <span className="game-preview-top">
        <span className="game-preview-brand">Futureonaut</span>
        <span className="game-preview-play" aria-hidden>
          <PlayIcon size={14} />
        </span>
      </span>
      <h3 className="game-preview-title">{title}</h3>
      {lede ? <p className="game-preview-lede">{lede}</p> : null}
      <span className="game-preview-meta">
        <span className="game-preview-chip">{topic}</span>
        <span className="game-preview-chip level">
          {t("level")} {difficulty}
        </span>
        {progressLabel ? <span className="game-preview-chip progress">{progressLabel}</span> : null}
      </span>
      {clampedPct !== null ? (
        <span className="game-preview-bar" aria-hidden>
          <span style={{ width: `${clampedPct}%` }} />
        </span>
      ) : null}
    </Link>
  );
}
