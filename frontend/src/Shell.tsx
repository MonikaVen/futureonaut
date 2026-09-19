import { NavLink, Outlet, Link, useLocation } from "react-router-dom";
import { useAuth } from "./auth";
import { UI_LANGS, useLanguage } from "./language";

export function Shell() {
  const { user, logout, loading } = useAuth();
  const { lang, setLang, t } = useLanguage();
  const playing = useLocation().pathname.startsWith("/play/");
  if (loading) return <div className="app-shell">Loading…</div>;

  return (
    <div className={playing ? "app-shell play-mode" : "app-shell"}>
      <header className="topnav">
        <NavLink to="/" className="brand">
          Futureonaut
        </NavLink>
        <nav className="nav-links">
          <NavLink to="/">{t("games")}</NavLink>
          {user && <NavLink to="/dashboard">{t("dashboard")}</NavLink>}
          {user && <NavLink to="/recommendations">{t("forYou")}</NavLink>}
          {user && (user.role === "creator" || user.role === "admin") && (
            <NavLink to="/creator">{t("creator")}</NavLink>
          )}
          {user?.role === "admin" && <NavLink to="/admin">{t("admin")}</NavLink>}
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
          {user ? (
            <>
              <span className="meta">
                {user.display_name} · {user.role}
              </span>
              <button className="btn secondary" type="button" onClick={logout}>
                {t("logout")}
              </button>
            </>
          ) : (
            <>
              <Link to="/login">{t("signIn")}</Link>
              <Link className="btn accent" to="/register">
                {t("signUp")}
              </Link>
            </>
          )}
        </nav>
      </header>

      {!playing && (
        <section className="mission">
          <p>{t("mission")}</p>
        </section>
      )}

      <Outlet />
    </div>
  );
}
