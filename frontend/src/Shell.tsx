import { NavLink, Outlet, Link } from "react-router-dom";
import { useAuth } from "./auth";
import { BrandLogo } from "./BrandLogo";
import { LanguageSelect, useLanguage } from "./language";

export function Shell() {
  const { user, logout, loading } = useAuth();
  const { t } = useLanguage();
  if (loading) {
    return (
      <div className="app-shell app-loading">
        <BrandLogo />
      </div>
    );
  }

  return (
    <div className="app-shell">
      <header className="topnav">
        <NavLink to="/" className="brand">
          <BrandLogo />
        </NavLink>
        <nav className="nav-links">
          <NavLink to="/">{t("games")}</NavLink>
          {user && <NavLink to="/dashboard">{t("dashboard")}</NavLink>}
          {user && <NavLink to="/recommendations">{t("forYou")}</NavLink>}
          {user && <NavLink to="/classrooms">{t("classrooms")}</NavLink>}
          {user && (user.role === "creator" || user.role === "admin") && (
            <NavLink to="/creator">{t("creator")}</NavLink>
          )}
          {user?.role === "admin" && <NavLink to="/admin">{t("admin")}</NavLink>}
          <LanguageSelect />
          {user ? (
            <div className="nav-user">
              <span className="nav-user-meta">
                {user.display_name}
                <span className="nav-user-role">{user.role}</span>
              </span>
              <button className="btn secondary btn-sm" type="button" onClick={logout}>
                {t("logout")}
              </button>
            </div>
          ) : (
            <div className="nav-auth">
              <Link to="/login">{t("signIn")}</Link>
              <Link className="btn accent btn-sm" to="/register">
                {t("signUp")}
              </Link>
            </div>
          )}
        </nav>
      </header>

      <section className="platform-cover" aria-label="Futureonaut">
        <img src="/cover.png" alt={t("coverAlt")} />
      </section>

      <Outlet />
    </div>
  );
}
