import { FormEvent, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { BrandLogo } from "../BrandLogo";
import { useAuth } from "../auth";
import { LanguageSelect, useLanguage } from "../language";

export function LoginPage() {
  const { user, login, loading } = useAuth();
  const { t } = useLanguage();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (!loading && user) return <Navigate to="/" replace />;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(email, password);
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-layout">
      <div className="auth-brand">
        <BrandLogo className="auth-brand-logo" />
        <p className="lede">{t("loginLede")}</p>
      </div>
      <LanguageSelect className="auth-lang-select" />
      <div className="panel">
        <form className="form" onSubmit={onSubmit}>
          <label>
            {t("email")}
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
          <label>
            {t("password")}
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
            />
          </label>
          {error && <div className="error">{error}</div>}
          <div className="row">
            <button className="btn accent" disabled={busy} type="submit">
              {busy ? t("signingIn") : t("signIn")}
            </button>
            <Link to="/register">{t("createAccount")}</Link>
          </div>
        </form>
      </div>
    </div>
  );
}

export function RegisterPage() {
  const { user, register, loading } = useAuth();
  const { t } = useLanguage();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (!loading && user) return <Navigate to="/" replace />;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await register(email, password, displayName);
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-layout">
      <div className="auth-brand">
        <BrandLogo className="auth-brand-logo" />
        <p className="lede">{t("registerLede")}</p>
      </div>
      <LanguageSelect className="auth-lang-select" />
      <div className="panel">
        <form className="form" onSubmit={onSubmit}>
          <label>
            {t("displayName")}
            <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
          </label>
          <label>
            {t("email")}
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
          <label>
            {t("password")}
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
            />
          </label>
          {error && <div className="error">{error}</div>}
          <div className="row">
            <button className="btn accent" disabled={busy} type="submit">
              {busy ? t("creating") : t("createAccount")}
            </button>
            <Link to="/login">{t("backToSignIn")}</Link>
          </div>
        </form>
      </div>
    </div>
  );
}
