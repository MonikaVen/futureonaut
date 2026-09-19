export const TOPICS = ["ML", "Physics", "Math"] as const;
export type Topic = (typeof TOPICS)[number];

export function primaryTopic(tags?: string[] | null): Topic {
  const hit = tags?.find((tag) => TOPICS.includes(tag as Topic));
  if (hit) return hit as Topic;
  if (tags?.includes("AI")) return "ML";
  return "ML";
}

export function posterKind(topic: string): "ai" | "physics" | "math" {
  const value = topic.toLowerCase();
  if (value === "physics") return "physics";
  if (value === "math") return "math";
  return "ai";
}
