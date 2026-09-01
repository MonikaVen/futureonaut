export type SharePlatform = "copy" | "x" | "facebook" | "linkedin";

/** Public URL used for Open Graph previews (crawler-friendly HTML). */
export function gameShareUrl(gameId: string): string {
  return `${window.location.origin}/share/${gameId}`;
}

/** Direct play URL for users already on the site. */
export function gamePlayUrl(gameId: string): string {
  return `${window.location.origin}/play/${gameId}`;
}

export function gameShareText(title: string, description?: string): string {
  const blurb = description ? ` — ${description}` : "";
  return `Play "${title}" on Futureonaut${blurb}`;
}

export function shareLinks(gameId: string, title: string, description?: string) {
  const url = encodeURIComponent(gameShareUrl(gameId));
  const text = encodeURIComponent(gameShareText(title, description));

  return {
    x: `https://twitter.com/intent/tweet?text=${text}&url=${url}`,
    facebook: `https://www.facebook.com/sharer/sharer.php?u=${url}`,
    linkedin: `https://www.linkedin.com/sharing/share-offsite/?url=${url}`,
  };
}

export async function copyGameLink(gameId: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(gameShareUrl(gameId));
    return true;
  } catch {
    return false;
  }
}

export async function nativeShareGame(
  gameId: string,
  title: string,
  description?: string
): Promise<boolean> {
  if (!navigator.share) return false;
  try {
    await navigator.share({
      title: `${title} · Futureonaut`,
      text: gameShareText(title, description),
      url: gameShareUrl(gameId),
    });
    return true;
  } catch {
    return false;
  }
}

export function openShareWindow(href: string) {
  window.open(href, "_blank", "noopener,noreferrer,width=600,height=520");
}
