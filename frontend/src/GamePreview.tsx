import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

type Props = {
  gameId: string;
  entryPath: string;
  title: string;
};

export function GamePreview({ gameId, entryPath, title }: Props) {
  const rootRef = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState(false);

  useEffect(() => {
    const el = rootRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setActive(true);
          observer.disconnect();
        }
      },
      { rootMargin: "120px" }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const src = `/api/games/${gameId}/files/${entryPath}`;

  return (
    <div className="game-preview" ref={rootRef}>
      {active ? (
        <iframe
          className="game-preview-frame"
          src={src}
          title={`${title} preview`}
          sandbox="allow-scripts allow-same-origin"
          loading="lazy"
          tabIndex={-1}
        />
      ) : (
        <div className="game-preview-skeleton" aria-hidden />
      )}
      <Link className="game-preview-overlay" to={`/play/${gameId}`} aria-label={`Play ${title}`} />
    </div>
  );
}
