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
    signIn: "Sign in",
    signUp: "Sign up",
    search: "Search games",
    topic: "Topic",
    level: "Level",
    sort: "Sort",
    language: "Language",
    play: "Play",
    translating: "Translating game…",
    detected: "Detected",
    mission:
      "Mission: help learners build intuition for ML, Physics, and Math through short playable challenges — practice freely, then sign in to keep your scores and get guidance.",
    guestPlayNote: "Playing as a guest — progress is saved on this device and merges when you sign in.",
    signInToTrack: "Sign in to track scores",
    runComplete: "Run complete!",
    copyScoreCard: "Copy score card",
    classrooms: "Classrooms",
    shareGame: "Share",
    share: "Share…",
    copyLink: "Copy link",
    linkCopied: "Copied!",
    like: "Like",
    comments: "Comments",
    postComment: "Post",
    commentPlaceholder: "Share your thoughts on this game…",
    signInToLike: "Sign in to like",
    signInToComment: "to leave a comment.",
    noComments: "No comments yet. Be the first!",
    deleteComment: "Delete",
    moderateComments: "Comments",
  },
  lt: {
    games: "Žaidimai",
    dashboard: "Skydelis",
    forYou: "Tau",
    creator: "Kūrėjas",
    admin: "Admin",
    logout: "Atsijungti",
    signIn: "Prisijungti",
    signUp: "Registruotis",
    search: "Ieškoti žaidimų",
    topic: "Tema",
    level: "Lygis",
    sort: "Rikiuoti",
    language: "Kalba",
    play: "Žaisti",
    translating: "Verčiama…",
    detected: "Aptikta",
    mission:
      "Misija: padėti mokytis ML, fizikos ir matematikos per trumpus žaidimus — žaisk laisvai, o prisijungęs išsaugosi rezultatus ir gausi rekomendacijas.",
    guestPlayNote: "Žaidžiama kaip svečias — šis rezultatas nebus išsaugotas.",
    signInToTrack: "Prisijunk, kad sektum rezultatus",
    shareGame: "Dalintis",
    share: "Dalintis…",
    copyLink: "Kopijuoti nuorodą",
    linkCopied: "Nukopijuota!",
  },
  de: {
    games: "Spiele",
    dashboard: "Übersicht",
    forYou: "Für dich",
    creator: "Creator",
    admin: "Admin",
    logout: "Abmelden",
    signIn: "Anmelden",
    signUp: "Registrieren",
    search: "Spiele suchen",
    topic: "Thema",
    level: "Level",
    sort: "Sortieren",
    language: "Sprache",
    play: "Spielen",
    translating: "Übersetzung…",
    detected: "Erkannt",
    mission:
      "Mission: Intuition für ML, Physik und Mathematik durch kurze Spiel-Challenges aufbauen — frei üben, einloggen für Scores und Empfehlungen.",
    guestPlayNote: "Gastmodus — dieser Lauf wird nicht gespeichert.",
    signInToTrack: "Anmelden, um Scores zu speichern",
    shareGame: "Teilen",
    share: "Teilen…",
    copyLink: "Link kopieren",
    linkCopied: "Kopiert!",
  },
  es: {
    games: "Juegos",
    dashboard: "Panel",
    forYou: "Para ti",
    creator: "Creador",
    admin: "Admin",
    logout: "Salir",
    signIn: "Entrar",
    signUp: "Registrarse",
    search: "Buscar juegos",
    topic: "Tema",
    level: "Nivel",
    sort: "Ordenar",
    language: "Idioma",
    play: "Jugar",
    translating: "Traduciendo…",
    detected: "Detectado",
    mission:
      "Misión: construir intuición en ML, Física y Matemáticas con retos jugables — practica libremente; inicia sesión para guardar puntuaciones.",
    guestPlayNote: "Jugando como invitado — esta partida no se guarda.",
    signInToTrack: "Inicia sesión para guardar",
    shareGame: "Compartir",
    share: "Compartir…",
    copyLink: "Copiar enlace",
    linkCopied: "¡Copiado!",
  },
  fr: {
    games: "Jeux",
    dashboard: "Tableau",
    forYou: "Pour toi",
    creator: "Créateur",
    admin: "Admin",
    logout: "Déconnexion",
    signIn: "Connexion",
    signUp: "S'inscrire",
    search: "Rechercher",
    topic: "Sujet",
    level: "Niveau",
    sort: "Trier",
    language: "Langue",
    play: "Jouer",
    translating: "Traduction…",
    detected: "Détecté",
    mission:
      "Mission : développer l'intuition en ML, physique et maths via de courts défis jouables — joue librement, connecte-toi pour garder tes scores.",
    guestPlayNote: "Mode invité — cette partie n'est pas enregistrée.",
    signInToTrack: "Se connecter pour suivre les scores",
    shareGame: "Partager",
    share: "Partager…",
    copyLink: "Copier le lien",
    linkCopied: "Copié !",
  },
  pl: {
    games: "Gry",
    dashboard: "Panel",
    forYou: "Dla ciebie",
    creator: "Twórca",
    admin: "Admin",
    logout: "Wyloguj",
    signIn: "Zaloguj",
    signUp: "Zarejestruj",
    search: "Szukaj gier",
    topic: "Temat",
    level: "Poziom",
    sort: "Sortuj",
    language: "Język",
    play: "Graj",
    translating: "Tłumaczenie…",
    detected: "Wykryto",
    mission:
      "Misja: budować intuicję w ML, fizyce i matematyce przez krótkie gry — graj swobodnie, zaloguj się, by zapisywać wyniki i dostawać wskazówki.",
    guestPlayNote: "Tryb gościa — ten wynik nie zostanie zapisany.",
    signInToTrack: "Zaloguj się, by śledzić wyniki",
    shareGame: "Udostępnij",
    share: "Udostępnij…",
    copyLink: "Kopiuj link",
    linkCopied: "Skopiowano!",
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
