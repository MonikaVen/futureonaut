import type { Game } from "./api";
import { GamePreview } from "./GamePreview";
import { GameSocial } from "./GameSocial";

type Props = {
  game: Game;
  topic: string;
  focusLabels: string[];
  onUpdate: (patch: Partial<Game>) => void;
};

export function GameCard({ game, topic, focusLabels, onUpdate }: Props) {
  return (
    <article className="game-tile">
      <GamePreview
        gameId={game.id}
        title={game.title}
        description={game.description}
        topic={topic}
        difficulty={game.difficulty}
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
