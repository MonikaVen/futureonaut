import { useEffect, useState } from "react";
import { NavLink, Outlet, Link, useLocation } from "react-router-dom";
import { useAuth } from "./auth";
import { BrandLogo } from "./BrandLogo";
import { LanguageSelect, useLanguage } from "./language";
import { ThemeToggle, useTheme } from "./theme";

export function Shell() {
  const { user, logout, loading } = useAuth();
  const { t } = useLanguage();
  const { theme } = useTheme();
  const location = useLocation();
  const [navOpen, setNavOpen] = useState(false);
  const isPlay = location.pathname.startsWith("/play/");

  useEffect(() => {
    setNavOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    document.body.classList.toggle("nav-open", navOpen);
    return () => document.body.classList.remove("nav-open");
  }, [navOpen]);

  useEffect(() => {
    document.body.classList.toggle("play-focus", isPlay);
    return () => document.body.classList.remove("play-focus");
  }, [isPlay]);

  if (loading) {
    return (
      <div className="app-shell app-loading">
        <BrandLogo />
      </div>
    );
  }

  return (
    <div className={`app-shell${isPlay ? " play-focus" : ""}`}>
      <header className="topnav">
        <div className="topnav-bar">
          <NavLink to="/" className="brand">
            <BrandLogo />
          </NavLink>
          <button
            type="button"
            className="nav-toggle"
            aria-expanded={navOpen}
            aria-controls="main-nav"
            aria-label={navOpen ? t("closeMenu") : t("openMenu")}
            onClick={() => setNavOpen((open) => !open)}
          >
            <span className="nav-toggle-icon" aria-hidden />
          </button>
          <nav id="main-nav" className={`nav-links${navOpen ? " open" : ""}`}>
            <div className="nav-pages">
              <NavLink to="/">{t("games")}</NavLink>
              {user && <NavLink to="/dashboard">{t("dashboard")}</NavLink>}
              {user && <NavLink to="/recommendations">{t("forYou")}</NavLink>}
              {user && <NavLink to="/classrooms">{t("classrooms")}</NavLink>}
              {user && (user.can_create_games || user.role === "creator" || user.role === "admin" || user.role === "teacher") && (
                <NavLink to="/creator">{t("creator")}</NavLink>
              )}
              {user?.role === "admin" && <NavLink to="/admin">{t("admin")}</NavLink>}
            </div>
            <div className="nav-end">
              <LanguageSelect />
              <ThemeToggle />
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
                  <Link className="btn secondary btn-sm" to="/login">
                    {t("signIn")}
                  </Link>
                  <Link className="btn accent btn-sm" to="/register">
                    {t("signUp")}
                  </Link>
                </div>
              )}
            </div>
          </nav>
        </div>
      </header>

      {!isPlay && (
        <section className={`platform-cover platform-cover-${theme}`} aria-label={t("coverAlt")}>
          <img
            src={theme === "dark" ? "/cover-dark.png" : "/cover.png"}
            alt=""
          />
          <div className="platform-cover-copy">
            <p className="platform-cover-brand">{t("coverBrand")}</p>
            <p className="platform-cover-tagline">{t("coverTagline")}</p>
          </div>
        </section>
      )}

      <Outlet />
    </div>
  );
}
