export const TOPICS = ["AI", "Physics", "Math"] as const;
export type Topic = (typeof TOPICS)[number];

export function primaryTopic(tags?: string[] | null): Topic {
  const hit = tags?.find((tag) => TOPICS.includes(tag as Topic));
  if (hit) return hit as Topic;
  if (tags?.includes("ML")) return "AI";
  return "AI";
}

export const NEW_GAME_MS = 7 * 24 * 60 * 60 * 1000;

export function isNewGame(game: { is_new?: boolean; created_at?: string }): boolean {
  if (typeof game.is_new === "boolean") return game.is_new;
  if (!game.created_at) return false;
  const created = Date.parse(game.created_at);
  return Number.isFinite(created) && Date.now() - created <= NEW_GAME_MS;
}

export function posterKind(topic: string): "ai" | "physics" | "math" {
  const value = topic.toLowerCase();
  if (value === "physics") return "physics";
  if (value === "math") return "math";
  return "ai";
}
