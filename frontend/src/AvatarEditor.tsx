import { useState } from "react";
import { api, type User } from "./api";
import { useAuth } from "./auth";
import { AvatarImage } from "./AvatarImage";
import { useLanguage } from "./language";

type Props = {
  compact?: boolean;
};

export function AvatarEditor({ compact = false }: Props) {
  const { user, refreshMe } = useAuth();
  const { t } = useLanguage();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  if (!user) return null;

  async function upload(file: File) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const body = new FormData();
      body.append("avatar", file);
      await api<User>("/api/auth/avatar", { method: "POST", body });
      await refreshMe();
      setMessage(t("avatarSaved"));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("uploadAvatar"));
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await api<User>("/api/auth/avatar", { method: "DELETE" });
      await refreshMe();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("removeAvatar"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={`avatar-editor${compact ? " compact" : ""}`}>
      <AvatarImage userId={user.id} name={user.display_name} hasAvatar={Boolean(user.has_avatar)} size={compact ? 56 : 88} />
      <div>
        <p className="meta">{t("avatarHelp")}</p>
        {error && <div className="error">{error}</div>}
        {message && <p className="meta">{message}</p>}
        <div className="form-actions avatar-editor-actions">
          <label className="btn secondary btn-sm">
            {busy ? t("savingAvatar") : t("uploadAvatar")}
            <input
              type="file"
              accept="image/png,image/jpeg,image/webp,image/gif"
              hidden
              disabled={busy}
              onChange={(e) => {
                const file = e.target.files?.[0];
                e.target.value = "";
                if (file) void upload(file);
              }}
            />
          </label>
          {user.has_avatar ? (
            <button className="btn secondary btn-sm" type="button" disabled={busy} onClick={() => void remove()}>
              {t("removeAvatar")}
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}
