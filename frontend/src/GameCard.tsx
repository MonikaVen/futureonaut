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

  return (
    <article className="game-tile">
      <GamePreview
        gameId={game.id}
        title={game.title}
        topic={topic}
        difficulty={game.difficulty}
      />
      <div className="game-tile-body">
        <h3>{game.title}</h3>
        <p className="meta game-tile-desc">{game.description || t("noDescription")}</p>
        <div className="tags">
          <span className="tag topic">{topic}</span>
          {focusLabels.map((label) => (
            <span key={label} className="tag focus">
              {label}
            </span>
          ))}
          <span className="tag">Lv {game.difficulty}</span>
        </div>
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
