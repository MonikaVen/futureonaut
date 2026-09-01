import { useState } from "react";
import { useLanguage } from "./language";
import {
  copyGameLink,
  nativeShareGame,
  openShareWindow,
  shareLinks,
  type SharePlatform,
} from "./share";

type Props = {
  gameId: string;
  title: string;
  description?: string;
  compact?: boolean;
};

export function GameShare({ gameId, title, description, compact = false }: Props) {
  const { t } = useLanguage();
  const [copied, setCopied] = useState(false);
  const links = shareLinks(gameId, title, description);
  const canNativeShare = typeof navigator !== "undefined" && !!navigator.share;

  async function handle(platform: SharePlatform) {
    if (platform === "copy") {
      const ok = await copyGameLink(gameId);
      if (ok) {
        setCopied(true);
        window.setTimeout(() => setCopied(false), 2000);
      }
      return;
    }
    if (platform === "native") {
      await nativeShareGame(gameId, title, description);
      return;
    }
    openShareWindow(links[platform]);
  }

  const items: Array<{ id: SharePlatform; label: string; show: boolean }> = [
    { id: "copy", label: copied ? t("linkCopied") : t("copyLink"), show: true },
    { id: "native", label: t("share"), show: canNativeShare },
    { id: "x", label: "X", show: true },
    { id: "facebook", label: "Facebook", show: !compact },
    { id: "linkedin", label: "LinkedIn", show: !compact },
    { id: "whatsapp", label: "WhatsApp", show: true },
  ];

  return (
    <div className={`share-bar${compact ? " compact" : ""}`} aria-label={t("shareGame")}>
      <span className="share-label">{t("shareGame")}</span>
      <div className="share-actions">
        {items
          .filter((item) => item.show)
          .map((item) => (
            <button
              key={item.id}
              type="button"
              className={`share-btn${item.id === "x" ? " share-btn-x" : ""}`}
              onClick={() => handle(item.id)}
            >
              {item.label}
            </button>
          ))}
      </div>
    </div>
  );
}
