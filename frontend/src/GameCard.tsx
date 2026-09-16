import type { Game } from "./api";
import { GamePreview } from "./GamePreview";
import { GameSocial } from "./GameSocial";
import { useLanguage } from "./language";

type Props = {
  game: Game;
  topic: string;
  focusLabels: string[];
  onUpdate: (patch: Partial<Game>) => void;
};

export function GameCard({ game, topic, focusLabels, onUpdate }: Props) {
  const { t } = useLanguage();
  const solved = Boolean(game.completed);
  const levelsDone = game.levels_completed ?? 0;
  const total = game.total_levels ?? null;
  const progressLabel = solved
    ? undefined
    : total
      ? `${t("level")} ${levelsDone}/${total}`
      : levelsDone
        ? `${t("level")} ${levelsDone}`
        : undefined;
  const progressPct =
    typeof game.progress_pct === "number"
      ? game.progress_pct
      : total && total > 0
        ? Math.round((levelsDone / total) * 100)
        : solved
          ? 100
          : null;

  return (
    <article className="game-tile">
      <GamePreview
        gameId={game.id}
        title={game.title}
        description={game.description}
        topic={topic}
        difficulty={game.difficulty}
        solved={solved}
        progressLabel={progressLabel}
        progressPct={progressPct}
        hasScreenshot={Boolean(game.has_screenshot)}
      />
      <div className="game-tile-body">
        {focusLabels.length > 0 ? (
          <div className="tags">
            {focusLabels.map((label) => (
              <span key={label} className="tag focus">
                {label}
              </span>
            ))}
          </div>
        ) : null}
        <GameSocial
          game={{
            ...game,
            like_count: game.like_count ?? 0,
            comment_count: game.comment_count ?? 0,
            liked_by_me: game.liked_by_me ?? false,
          }}
          compact
          shareTitle={game.title}
          shareDescription={game.description}
          onUpdate={onUpdate}
        />
      </div>
    </article>
  );
}
