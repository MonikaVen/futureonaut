import { FormEvent, useMemo, useState } from "react";
import type { GameDraft } from "./api";
import { useLanguage } from "./language";
import { useTheme } from "./theme";

type Props = {
  draft: GameDraft;
  apiKey: string;
  busy: boolean;
  onRevise: (message: string) => Promise<void>;
  onPublish: () => Promise<void>;
  onDiscard: () => Promise<void>;
};

export function CreatorDraftStudio({ draft, apiKey, busy, onRevise, onPublish, onDiscard }: Props) {
  const { t, lang } = useLanguage();
  const { theme } = useTheme();
  const [note, setNote] = useState("");
  const preview = useMemo(() => {
    const params = new URLSearchParams({
      theme,
      lang,
      r: draft.updated_at,
    });
    return `/api/games/drafts/${draft.id}/files/${draft.preview_path || "index.html"}?${params.toString()}`;
  }, [draft.id, draft.preview_path, draft.updated_at, theme, lang]);

  async function send(e: FormEvent) {
    e.preventDefault();
    const message = note.trim();
    if (!message || busy) return;
    await onRevise(message);
    setNote("");
  }

  return (
    <div className="draft-studio">
      <div className="draft-preview-col">
        <div className="draft-preview-head">
          <h2>{t("draftPreview")}</h2>
          <p className="meta">{draft.title}</p>
        </div>
        {draft.warnings.length > 0 ? (
          <div className="draft-warnings">{t("draftWarnings")}</div>
        ) : null}
        <iframe
          key={preview}
          className="frame draft-frame"
          title={draft.title}
          src={preview}
          sandbox="allow-scripts allow-forms"
          referrerPolicy="no-referrer"
        />
      </div>
      <div className="draft-chat-col">
        <h2>{t("draftChat")}</h2>
        <p className="meta">{t("gameDraftReady")}</p>
        <ul className="draft-messages">
          {draft.messages.map((msg, idx) => (
            <li key={`${msg.role}-${idx}`} className={`draft-msg draft-msg-${msg.role}`}>
              <span className="draft-msg-role">{msg.role === "user" ? t("you") : t("assistant")}</span>
              <p>{msg.content}</p>
            </li>
          ))}
        </ul>
        <form className="draft-chat-form" onSubmit={send}>
          <label>
            {t("reviseGame")}
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={4}
              placeholder={t("draftChatPlaceholder")}
              disabled={busy}
              required
            />
          </label>
          <div className="form-actions">
            <button className="btn accent" type="submit" disabled={busy || !apiKey || note.trim().length < 2}>
              {busy ? t("revisingGame") : t("sendRevision")}
            </button>
            <button className="btn" type="button" disabled={busy} onClick={() => onPublish()}>
              {busy ? t("publishingGame") : t("publishGame")}
            </button>
            <button className="btn danger" type="button" disabled={busy} onClick={() => onDiscard()}>
              {t("discardDraft")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
