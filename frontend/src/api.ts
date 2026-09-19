export type Role = "admin" | "creator" | "learner";

export interface User {
  id: string;
  email: string;
  display_name: string;
  role: Role;
  created_at: string;
}

export interface Game {
  id: string;
  title: string;
  description: string;
  owner_id: string;
  owner_name?: string | null;
  source: "upload" | "template" | "ai";
  topic_tags: string[];
  difficulty: number;
  entry_path: string;
  template_type: string | null;
  source_language?: string;
  created_at: string;
  play_url?: string | null;
  like_count?: number;
  comment_count?: number;
  view_count?: number;
  liked_by_me?: boolean;
  completed?: boolean;
  levels_completed?: number;
  total_levels?: number | null;
  progress_pct?: number | null;
  has_screenshot?: boolean;
}

export interface Session {
  id: string;
  user_id: string;
  game_id: string;
  started_at: string;
  ended_at: string | null;
  total_points: number;
  total_time_ms: number;
  correct_count: number;
  attempt_count: number;
  game_title?: string | null;
}

export interface DashboardStats {
  total_sessions: number;
  total_points: number;
  avg_accuracy: number;
  avg_task_time_ms: number;
  recent_sessions: Session[];
  per_game: Array<Record<string, unknown>>;
  by_topic: Array<Record<string, unknown>>;
}

export interface Recommendation {
  game: Game;
  reason: string;
  score: number;
}

export interface PlatformStats {
  users: number;
  games: number;
  sessions: number;
  creators: number;
  learners: number;
}

const ACCESS_KEY = "lp_access";
const REFRESH_KEY = "lp_refresh";

export function getAccessToken() {
  return localStorage.getItem(ACCESS_KEY);
}

export function setTokens(access: string, refresh: string) {
  localStorage.setItem(ACCESS_KEY, access);
  localStorage.setItem(REFRESH_KEY, refresh);
}

export function clearTokens() {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

async function refreshAccess(): Promise<string | null> {
  const refresh = localStorage.getItem(REFRESH_KEY);
  if (!refresh) return null;
  const res = await fetch("/api/auth/refresh", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refresh }),
  });
  if (!res.ok) {
    clearTokens();
    return null;
  }
  const data = await res.json();
  setTokens(data.access_token, data.refresh_token);
  return data.access_token as string;
}

export async function api<T>(
  path: string,
  options: RequestInit = {},
  retry = true
): Promise<T> {
  const headers = new Headers(options.headers || {});
  const token = getAccessToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(path, { ...options, headers });
  if (res.status === 401 && retry) {
    const next = await refreshAccess();
    if (next) return api<T>(path, options, false);
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const err = await res.json();
      detail = typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail);
    } catch {
      /* ignore */
    }
    throw new Error(detail || "Request failed");
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}
