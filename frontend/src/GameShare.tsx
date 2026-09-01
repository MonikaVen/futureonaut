import { useEffect, useRef, useState } from "react";
import { ShareIcon } from "./ShareIcon";
import { useLanguage } from "./language";
import { copyGameLink, openShareWindow, shareLinks, type SharePlatform } from "./share";

type Props = {
  gameId: string;
  title: string;
  description?: string;
  compact?: boolean;
};

const SOCIAL_ITEMS: Array<{ id: Exclude<SharePlatform, "native" | "whatsapp">; label: string }> = [
  { id: "x", label: "X" },
  { id: "facebook", label: "Facebook" },
  { id: "linkedin", label: "LinkedIn" },
];

function ShareIconButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button type="button" className="share-menu-item" onClick={onClick}>
      {label}
    </button>
  );
}

export function GameShare({ gameId, title, description, compact = false }: Props) {
  const { t } = useLanguage();
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const links = shareLinks(gameId, title, description);

  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open]);

  async function handle(platform: SharePlatform) {
    if (platform === "copy") {
      const ok = await copyGameLink(gameId);
      if (ok) {
        setCopied(true);
        window.setTimeout(() => setCopied(false), 2000);
      }
      setOpen(false);
      return;
    }
    if (platform === "x" || platform === "facebook" || platform === "linkedin") {
      openShareWindow(links[platform]);
      setOpen(false);
    }
  }

  if (compact) {
    return (
      <div className="share-menu" ref={menuRef}>
        <button
          type="button"
          className="share-icon-btn"
          aria-label={t("shareGame")}
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
        >
          <ShareIcon />
        </button>
        {open && (
          <div className="share-menu-popover" role="menu">
            {SOCIAL_ITEMS.map((item) => (
              <ShareIconButton key={item.id} label={item.label} onClick={() => handle(item.id)} />
            ))}
            <ShareIconButton
              label={copied ? t("linkCopied") : t("copyLink")}
              onClick={() => handle("copy")}
            />
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="share-bar" aria-label={t("shareGame")}>
      <span className="share-label">{t("shareGame")}</span>
      <div className="share-actions">
        {SOCIAL_ITEMS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`share-btn${item.id === "x" ? " share-btn-x" : ""}`}
            onClick={() => handle(item.id)}
          >
            {item.label}
          </button>
        ))}
        <button type="button" className="share-btn" onClick={() => handle("copy")}>
          {copied ? t("linkCopied") : t("copyLink")}
        </button>
      </div>
    </div>
  );
}
