import type { StoredConversation } from "@/lib/types";

const STORAGE_KEY = "factory-graph-rca-history";
const MAX_CONVERSATIONS = 20;

export function readHistory(): StoredConversation[] {
  if (typeof window === "undefined") return [];
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveConversation(
  conversation: StoredConversation,
): StoredConversation[] {
  const next = [
    conversation,
    ...readHistory().filter((item) => item.id !== conversation.id),
  ].slice(0, MAX_CONVERSATIONS);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  return next;
}

export function clearHistory() {
  localStorage.removeItem(STORAGE_KEY);
}

export function removeConversation(id: string) {
  const next = readHistory().filter((item) => item.id !== id);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  return next;
}
