type Props = {
  userId?: string | null;
  name?: string;
  hasAvatar?: boolean;
  size?: number;
  className?: string;
};

function initials(name?: string) {
  const parts = (name || "").trim().split(/\s+/).filter(Boolean);
  const letters = parts.slice(0, 2).map((part) => part[0]?.toUpperCase() || "").join("");
  return letters || "F";
}

export function AvatarImage({ userId, name, hasAvatar = false, size = 40, className = "" }: Props) {
  const src = userId && hasAvatar ? `/api/users/${userId}/avatar` : "";
  return (
    <span className={`avatar${className ? ` ${className}` : ""}`} style={{ width: size, height: size, fontSize: Math.round(size * 0.38) }}>
      {src ? <img src={src} alt="" width={size} height={size} /> : <span>{initials(name)}</span>}
    </span>
  );
}
