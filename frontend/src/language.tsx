import {
  createContext,
  createElement,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

const STORAGE_KEY = "futureonaut_lang";

export const UI_LANGS = [
  { code: "en", label: "English" },
  { code: "lt", label: "Lietuvių" },
  { code: "de", label: "Deutsch" },
  { code: "es", label: "Español" },
  { code: "fr", label: "Français" },
  { code: "pl", label: "Polski" },
] as const;

type LangCode = (typeof UI_LANGS)[number]["code"];

const COPY: Record<LangCode, Record<string, string>> = {
  en: {
    games: "Games",
    dashboard: "Dashboard",
    forYou: "For you",
    creator: "Creator",
    admin: "Admin",
    logout: "Log out",
    search: "Search games",
    topic: "Topic",
    level: "Level",
    sort: "Sort",
    language: "Language",
    play: "Play",
    translating: "Translating game…",
    detected: "Detected",
  },
  lt: {
    games: "Žaidimai",
    dashboard: "Skydelis",
    forYou: "Tau",
    creator: "Kūrėjas",
    admin: "Admin",
    logout: "Atsijungti",
    search: "Ieškoti žaidimų",
    topic: "Tema",
    level: "Lygis",
    sort: "Rikiuoti",
    language: "Kalba",
    play: "Žaisti",
    translating: "Verčiama…",
    detected: "Aptikta",
  },
  de: {
    games: "Spiele",
    dashboard: "Übersicht",
    forYou: "Für dich",
    creator: "Creator",
    admin: "Admin",
    logout: "Abmelden",
    search: "Spiele suchen",
    topic: "Thema",
    level: "Level",
    sort: "Sortieren",
    language: "Sprache",
    play: "Spielen",
    translating: "Übersetzung…",
    detected: "Erkannt",
  },
  es: {
    games: "Juegos",
    dashboard: "Panel",
    forYou: "Para ti",
    creator: "Creador",
    admin: "Admin",
    logout: "Salir",
    search: "Buscar juegos",
    topic: "Tema",
    level: "Nivel",
    sort: "Ordenar",
    language: "Idioma",
    play: "Jugar",
    translating: "Traduciendo…",
    detected: "Detectado",
  },
  fr: {
    games: "Jeux",
    dashboard: "Tableau",
    forYou: "Pour toi",
    creator: "Créateur",
    admin: "Admin",
    logout: "Déconnexion",
    search: "Rechercher",
    topic: "Sujet",
    level: "Niveau",
    sort: "Trier",
    language: "Langue",
    play: "Jouer",
    translating: "Traduction…",
    detected: "Détecté",
  },
  pl: {
    games: "Gry",
    dashboard: "Panel",
    forYou: "Dla ciebie",
    creator: "Twórca",
    admin: "Admin",
    logout: "Wyloguj",
    search: "Szukaj gier",
    topic: "Temat",
    level: "Poziom",
    sort: "Sortuj",
    language: "Język",
    play: "Graj",
    translating: "Tłumaczenie…",
    detected: "Wykryto",
  },
};

interface LangState {
  lang: LangCode;
  setLang: (code: LangCode) => void;
  t: (key: string) => string;
}

const LangContext = createContext<LangState | null>(null);

function readInitial(): LangCode {
  const saved = localStorage.getItem(STORAGE_KEY) as LangCode | null;
  if (saved && UI_LANGS.some((l) => l.code === saved)) return saved;
  const nav = (navigator.language || "en").slice(0, 2).toLowerCase();
  if (UI_LANGS.some((l) => l.code === nav)) return nav as LangCode;
  return "en";
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<LangCode>(readInitial);

  const setLang = (code: LangCode) => {
    localStorage.setItem(STORAGE_KEY, code);
    setLangState(code);
  };

  const value = useMemo(
    () => ({
      lang,
      setLang,
      t: (key: string) => COPY[lang][key] || COPY.en[key] || key,
    }),
    [lang]
  );

  return createElement(LangContext.Provider, { value }, children);
}

export function useLanguage() {
  const ctx = useContext(LangContext);
  if (!ctx) throw new Error("useLanguage outside provider");
  return ctx;
}
