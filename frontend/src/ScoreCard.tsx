import { useState } from "react";

type Props = {
  sessionId: string;
  gameTitle: string;
  points: number;
  correct: number;
  attempts: number;
  levelsCompleted?: number;
  totalLevels?: number | null;
};

export function ScoreCard({
  sessionId,
  gameTitle,
  points,
  correct,
  attempts,
  levelsCompleted,
  totalLevels,
}: Props) {
  const [copied, setCopied] = useState(false);
  const accuracy = attempts ? Math.round((correct / attempts) * 100) : 0;
  const cardUrl = `${window.location.origin}/share/score/${sessionId}/card.svg`;
  const shareText = `I scored ${points} pts (${accuracy}% accuracy) on ${gameTitle} on Futureonaut!`;

  async function copyLink() {
    const url = `${window.location.origin}/share/score/${sessionId}/card.svg`;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      /* ignore */
    }
  }

  async function nativeShare() {
    if (!navigator.share) return;
    try {
      await navigator.share({ title: gameTitle, text: shareText, url: cardUrl });
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="score-card-panel">
      <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>Run complete!</h2>
      <p className="meta">{gameTitle}</p>
      <div className="score-card-stats">
        <div className="stat">
          <span className="meta">Points</span>
          <b>{points}</b>
        </div>
        <div className="stat">
          <span className="meta">Accuracy</span>
          <b>{accuracy}%</b>
        </div>
        {levelsCompleted ? (
          <div className="stat">
            <span className="meta">Levels</span>
            <b>
              {levelsCompleted}
              {totalLevels ? `/${totalLevels}` : ""}
            </b>
          </div>
        ) : null}
      </div>
      <img className="score-card-preview" src={cardUrl} alt={`Score card for ${gameTitle}`} />
      <div className="row">
        <button className="btn accent" type="button" onClick={copyLink}>
          {copied ? "Copied!" : "Copy score card"}
        </button>
        {typeof navigator !== "undefined" && navigator.share ? (
          <button className="btn secondary" type="button" onClick={nativeShare}>
            Share…
          </button>
        ) : null}
      </div>
    </div>
  );
}
