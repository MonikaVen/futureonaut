import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, type CreatorProfile, type Game } from "../api";
import { AvatarEditor } from "../AvatarEditor";
import { AvatarImage } from "../AvatarImage";
import { GameCard } from "../GameCard";
import { GameShare } from "../GameShare";
import { primaryTopic } from "../gameMeta";
import { useAuth } from "../auth";
import { useLanguage } from "../language";
import { creatorShareUrl } from "../share";

export function CreatorProfilePage() {
  const { slug } = useParams();
  const { user } = useAuth();
  const { t } = useLanguage();
  const [profile, setProfile] = useState<CreatorProfile | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!slug) return;
    api<CreatorProfile>(`/api/creators/${encodeURIComponent(slug)}`)
      .then(setProfile)
      .catch((err) => setError(err.message));
  }, [slug]);

  function updateGame(id: string, patch: Partial<Game>) {
    setProfile((current) =>
      current
        ? { ...current, games: current.games.map((game) => (game.id === id ? { ...game, ...patch } : game)) }
        : current
    );
  }

  if (error) {
    return (
      <div>
        <div className="error">{error}</div>
        <Link to="/creators">{t("creators")}</Link>
      </div>
    );
  }
  if (!profile) return <p className="meta">{t("loadingCreator")}</p>;

  const isSelf = user?.id === profile.id;
  const shareUrl = creatorShareUrl(profile.slug);

  return (
    <div>
      <section className="hero creator-profile-hero">
        <AvatarImage userId={profile.id} name={profile.display_name} hasAvatar={profile.has_avatar} size={96} />
        <div>
          <h1>{profile.display_name}</h1>
          <p>
            {profile.game_count} {profile.game_count === 1 ? t("gameOne") : t("gameMany")} · @{profile.slug}
          </p>
          <GameShare shareUrl={shareUrl} title={profile.display_name} description={t("creatorsLede")} />
        </div>
      </section>
      {isSelf ? (
        <div className="panel" style={{ marginBottom: 16 }}>
          <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>{t("yourAvatar")}</h2>
          <AvatarEditor compact />
        </div>
      ) : null}
      <section className="preview-card-section">
        <div className="grid">
          {profile.games.map((game) => (
            <GameCard
              key={game.id}
              game={game}
              topic={primaryTopic(game.topic_tags)}
              focusLabels={[]}
              onUpdate={(patch) => updateGame(game.id, patch)}
            />
          ))}
        </div>
        {!profile.games.length ? <p className="meta">{t("noCreatorGames")}</p> : null}
      </section>
    </div>
  );
}
