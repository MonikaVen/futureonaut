import { useState, type CSSProperties } from "react";
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
  const [photoFailed, setPhotoFailed] = useState(false);

  return (
    <Link
      className={`game-preview topic-${kind}${photoFailed ? "" : " has-photo"}`}
      to={`/play/${gameId}`}
      aria-label={`${t("play")} ${title}`}
      style={orbStyle(gameId)}
    >
      {!photoFailed ? (
        <img
          className="game-preview-photo"
          src={`/share/${gameId}/card.png`}
          alt=""
          loading="lazy"
          decoding="async"
          onError={() => setPhotoFailed(true)}
        />
      ) : null}
      <span className="game-preview-top">
        {photoFailed ? <span className="game-preview-brand">Futureonaut</span> : <span />}
        <span className="game-preview-play" aria-hidden>
          <PlayIcon size={14} />
        </span>
      </span>
      {photoFailed ? (
        <>
          <h3 className="game-preview-title">{title}</h3>
          {lede ? <p className="game-preview-lede">{lede}</p> : null}
          <span className="game-preview-meta">
            <span className="game-preview-chip">{topic}</span>
            <span className="game-preview-chip level">
              {t("level")} {difficulty}
            </span>
            {progressLabel ? <span className="game-preview-chip progress">{progressLabel}</span> : null}
          </span>
        </>
      ) : progressLabel ? (
        <span className="game-preview-meta">
          <span className="game-preview-chip progress">{progressLabel}</span>
        </span>
      ) : null}
      {clampedPct !== null ? (
        <span className="game-preview-bar" aria-hidden>
          <span style={{ width: `${clampedPct}%` }} />
        </span>
      ) : null}
    </Link>
  );
}
