import { NavLink, Outlet, Navigate } from "react-router-dom";
import { useAuth } from "./auth";
import { UI_LANGS, useLanguage } from "./language";

export function Shell() {
  const { user, logout, loading } = useAuth();
  const { lang, setLang, t } = useLanguage();
  if (loading) return <div className="app-shell">Loading…</div>;
  if (!user) return <Navigate to="/login" replace />;

  return (
    <div className="app-shell">
      <header className="topnav">
        <NavLink to="/" className="brand">
          Futureonaut
        </NavLink>
        <nav className="nav-links">
          <NavLink to="/">{t("games")}</NavLink>
          <NavLink to="/dashboard">{t("dashboard")}</NavLink>
          <NavLink to="/recommendations">{t("forYou")}</NavLink>
          {(user.role === "creator" || user.role === "admin") && (
            <NavLink to="/creator">{t("creator")}</NavLink>
          )}
          {user.role === "admin" && <NavLink to="/admin">{t("admin")}</NavLink>}
          <label className="lang-select">
            <span className="meta">{t("language")}</span>
            <select
              value={lang}
              onChange={(e) => setLang(e.target.value as typeof lang)}
              aria-label={t("language")}
            >
              {UI_LANGS.map((l) => (
                <option key={l.code} value={l.code}>
                  {l.label}
                </option>
              ))}
            </select>
          </label>
          <span className="meta">
            {user.display_name} · {user.role}
          </span>
          <button className="btn secondary" type="button" onClick={logout}>
            {t("logout")}
          </button>
        </nav>
      </header>
      <Outlet />
    </div>
  );
}
