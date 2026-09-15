import {
  createContext,
  createElement,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { MoonIcon, SunIcon } from "./Icons";
import { useLanguage } from "./language";

export const THEME_STORAGE_KEY = "futureonaut_theme";
export type Theme = "light" | "dark";

interface ThemeState {
  theme: Theme;
  setTheme: (theme: Theme) => void;
}

const ThemeContext = createContext<ThemeState | null>(null);

export function readStoredTheme(): Theme {
  try {
    const saved = localStorage.getItem(THEME_STORAGE_KEY);
    if (saved === "dark" || saved === "light") return saved;
  } catch {
    /* ignore */
  }
  return "light";
}

export function applyTheme(theme: Theme) {
  document.documentElement.setAttribute("data-theme", theme);
  document.documentElement.style.colorScheme = theme;
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute("content", theme === "dark" ? "#050810" : "#f3f6fa");
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(() => {
    const initial = readStoredTheme();
    applyTheme(initial);
    return initial;
  });

  const setTheme = (next: Theme) => {
    localStorage.setItem(THEME_STORAGE_KEY, next);
    applyTheme(next);
    setThemeState(next);
  };

  const value = useMemo(() => ({ theme, setTheme }), [theme]);
  return createElement(ThemeContext.Provider, { value }, children);
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme outside provider");
  return ctx;
}

export function ThemeToggle({ className = "" }: { className?: string }) {
  const { theme, setTheme } = useTheme();
  const { t } = useLanguage();

  return (
    <div
      className={`theme-toggle${className ? ` ${className}` : ""}`}
      role="group"
      aria-label={t("theme")}
    >
      <button
        type="button"
        className={theme === "light" ? "active" : ""}
        aria-pressed={theme === "light"}
        onClick={() => setTheme("light")}
      >
        <SunIcon size={14} />
        <span>{t("lightMode")}</span>
      </button>
      <button
        type="button"
        className={theme === "dark" ? "active" : ""}
        aria-pressed={theme === "dark"}
        onClick={() => setTheme("dark")}
      >
        <MoonIcon size={14} />
        <span>{t("darkMode")}</span>
      </button>
    </div>
  );
}
