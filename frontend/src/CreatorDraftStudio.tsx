import { FormEvent, useMemo, useState } from "react";
import type { GameDraft } from "./api";
import { GameFrame } from "./GameFrame";
import { useLanguage } from "./language";
import { useTheme } from "./theme";

type Props = {
  draft: GameDraft | null;
  apiKey: string;
  busy: boolean;
  onSend: (message: string) => Promise<void>;
  onDeploy: () => Promise<void>;
  onDiscard: () => Promise<void>;
  onNew: () => void;
};

export function CreatorDraftStudio({
  draft,
  apiKey,
  busy,
  onSend,
  onDeploy,
  onDiscard,
  onNew,
}: Props) {
  const { t, lang } = useLanguage();
  const { theme } = useTheme();
  const [note, setNote] = useState("");
  const preview = useMemo(() => {
    if (!draft) return "";
    const params = new URLSearchParams({
      theme,
      lang,
      r: draft.updated_at,
    });
    const file = draft.preview_path || "index.html";
    if (!draft.preview_token) return "";
    return `/api/games/drafts/${draft.id}/t/${encodeURIComponent(draft.preview_token)}/${file}?${params.toString()}`;
  }, [draft, theme, lang]);

  async function send(e: FormEvent) {
    e.preventDefault();
    const message = note.trim();
    if (!message || busy) return;
    await onSend(message);
    setNote("");
  }

  return (
    <div className="draft-studio">
      <div className="draft-preview-col">
        <div className="draft-preview-head">
          <h2>{t("draftPreview")}</h2>
          <p className="meta">{draft ? draft.title : t("chatEmptyPreview")}</p>
        </div>
        {draft?.warnings.length ? <div className="draft-warnings">{t("draftWarnings")}</div> : null}
        {preview ? (
          <GameFrame key={preview} className="frame draft-frame" title={draft?.title || t("draftPreview")} src={preview} />
        ) : (
          <div className="draft-frame draft-frame-empty">
            <p>{t("chatEmptyPreview")}</p>
          </div>
        )}
      </div>
      <div className="draft-chat-col">
        <h2>{t("draftChat")}</h2>
        <p className="meta">{t("gameDraftReady")}</p>
        <ul className="draft-messages">
          {(draft?.messages || []).map((msg, idx) => (
            <li key={`${msg.role}-${idx}`} className={`draft-msg draft-msg-${msg.role}`}>
              <span className="draft-msg-role">{msg.role === "user" ? t("you") : t("assistant")}</span>
              <p>{msg.content}</p>
            </li>
          ))}
        </ul>
        <form className="draft-chat-form" onSubmit={send}>
          <label>
            {draft ? t("reviseGame") : t("generateGame")}
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={5}
              placeholder={t("draftChatPlaceholder")}
              disabled={busy}
              required
            />
          </label>
          <div className="form-actions">
            <button className="btn accent" type="submit" disabled={busy || !apiKey || note.trim().length < 2}>
              {busy ? t("revisingGame") : t("sendRevision")}
            </button>
            <button className="btn" type="button" disabled={busy || !draft} onClick={() => onDeploy()}>
              {busy ? t("publishingGame") : t("publishGame")}
            </button>
            {draft ? (
              <>
                <button className="btn secondary" type="button" disabled={busy} onClick={onNew}>
                  {t("newGameChat")}
                </button>
                <button className="btn danger" type="button" disabled={busy} onClick={() => onDiscard()}>
                  {t("discardDraft")}
                </button>
              </>
            ) : null}
          </div>
        </form>
      </div>
    </div>
  );
}
