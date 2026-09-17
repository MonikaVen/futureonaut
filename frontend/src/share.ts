export type SharePlatform = "copy" | "x" | "facebook" | "linkedin";

/** Public URL used for Open Graph previews (crawler-friendly HTML). */
export function gameShareUrl(gameId: string): string {
  return `${window.location.origin}/share/${gameId}`;
}

export function creatorProfilePath(slug: string): string {
  return `/u/${encodeURIComponent(slug)}`;
}

export function creatorShareUrl(slug: string): string {
  return `${window.location.origin}/share/u/${encodeURIComponent(slug)}`;
}

/** 1200×630 PNG snapshot used on catalog cards and social share photos. */
export function gameShareImageUrl(gameId: string): string {
  return `${window.location.origin}/share/${gameId}/card.png`;
}

/** Direct play URL for users already on the site. */
export function gamePlayPath(game: { id: string; handle?: string | null }): string {
  const slug = (game.handle || "").trim() || game.id;
  return `/play/${slug}`;
}

export function gamePlayUrl(gameId: string): string {
  return `${window.location.origin}/play/${gameId}`;
}

export function gameShareText(title: string, description?: string): string {
  const blurb = description ? ` — ${description}` : "";
  return `Play "${title}" on Futureonaut${blurb}`;
}

export function shareLinksFor(url: string, text: string) {
  const encodedUrl = encodeURIComponent(url);
  const encodedText = encodeURIComponent(text);
  return {
    x: `https://twitter.com/intent/tweet?text=${encodedText}&url=${encodedUrl}`,
    facebook: `https://www.facebook.com/sharer/sharer.php?u=${encodedUrl}`,
    linkedin: `https://www.linkedin.com/sharing/share-offsite/?url=${encodedUrl}`,
  };
}

export function shareLinks(gameId: string, title: string, description?: string) {
  return shareLinksFor(gameShareUrl(gameId), gameShareText(title, description));
}

export async function copyLink(url: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(url);
    return true;
  } catch {
    return false;
  }
}

export async function copyGameLink(gameId: string): Promise<boolean> {
  return copyLink(gameShareUrl(gameId));
}

async function gameShareImageFile(gameId: string, title: string): Promise<File | null> {
  try {
    const res = await fetch(gameShareImageUrl(gameId));
    if (!res.ok) return null;
    const blob = await res.blob();
    const safe = title.replace(/[^\w.-]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40) || "game";
    return new File([blob], `${safe}.png`, { type: blob.type || "image/png" });
  } catch {
    return null;
  }
}

export async function nativeShareGame(
  gameId: string,
  title: string,
  description?: string
): Promise<boolean> {
  if (!navigator.share) return false;
  const payload: ShareData = {
    title: `${title} · Futureonaut`,
    text: gameShareText(title, description),
    url: gameShareUrl(gameId),
  };
  try {
    const photo = await gameShareImageFile(gameId, title);
    if (photo && navigator.canShare?.({ files: [photo] })) {
      await navigator.share({ ...payload, files: [photo] });
      return true;
    }
    await navigator.share(payload);
    return true;
  } catch {
    return false;
  }
}

export function openShareWindow(href: string) {
  window.open(href, "_blank", "noopener,noreferrer,width=600,height=520");
}
