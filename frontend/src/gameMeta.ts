export const TOPICS = ["AI", "Physics", "Math"] as const;
export type Topic = (typeof TOPICS)[number];

export function primaryTopic(tags?: string[] | null): Topic {
  const hit = tags?.find((tag) => TOPICS.includes(tag as Topic));
  if (hit) return hit as Topic;
  if (tags?.includes("ML")) return "AI";
  return "AI";
}

export function posterKind(topic: string): "ai" | "physics" | "math" {
  const value = topic.toLowerCase();
  if (value === "physics") return "physics";
  if (value === "math") return "math";
  return "ai";
}
