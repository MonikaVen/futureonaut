import { Link } from "react-router-dom";
import { PlayIcon } from "./Icons";
import { useLanguage } from "./language";

type Props = {
  gameId: string;
  title: string;
  topic: string;
  difficulty: number;
};

function posterTopic(topic: string): "ai" | "physics" | "math" {
  const value = topic.toLowerCase();
  if (value === "physics") return "physics";
  if (value === "math") return "math";
  return "ai";
}

export function GamePreview({ gameId, title, topic, difficulty }: Props) {
  const { t } = useLanguage();
  const kind = posterTopic(topic);

  return (
    <Link
      className={`game-poster topic-${kind}`}
      to={`/play/${gameId}`}
      aria-label={`${t("play")} ${title}`}
    >
      <span className="game-poster-topic">{topic}</span>
      <span className="game-poster-play" aria-hidden>
        <PlayIcon size={22} />
      </span>
      <span className="game-poster-level">Lv {difficulty}</span>
    </Link>
  );
}
