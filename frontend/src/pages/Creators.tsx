import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type CreatorPublic } from "../api";
import { AvatarImage } from "../AvatarImage";
import { useLanguage } from "../language";

export function CreatorsPage() {
  const { t } = useLanguage();
  const [creators, setCreators] = useState<CreatorPublic[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api<CreatorPublic[]>("/api/creators")
      .then(setCreators)
      .catch((err: Error) => setError(err.message));
  }, []);

  return (
    <div>
      <section className="hero">
        <h1>{t("creators")}</h1>
        <p>{t("creatorsLede")}</p>
      </section>
      {error && <div className="error">{error}</div>}
      <div className="creator-directory">
        {creators.map((creator) => (
          <Link key={creator.id} className="creator-card" to={`/u/${creator.slug}`}>
            <AvatarImage userId={creator.id} name={creator.display_name} hasAvatar={creator.has_avatar} size={72} />
            <span>
              <strong>{creator.display_name}</strong>
              <span className="meta">
                {creator.game_count} {creator.game_count === 1 ? t("gameOne") : t("gameMany")}
              </span>
            </span>
          </Link>
        ))}
        {!creators.length && !error ? <p className="meta">{t("noCreators")}</p> : null}
      </div>
    </div>
  );
}
