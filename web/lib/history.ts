import type { StoredConversation } from "@/lib/types";

const STORAGE_KEY = "factory-graph-rca-history";
const MAX_CONVERSATIONS = 20;

function key(projectId: string) {
  return `${STORAGE_KEY}:${projectId}`;
}

export function readHistory(projectId: string): StoredConversation[] {
  if (typeof window === "undefined") return [];
  try {
    const parsed = JSON.parse(localStorage.getItem(key(projectId)) ?? "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveConversation(
  conversation: StoredConversation,
  projectId: string,
): StoredConversation[] {
  const next = [
    conversation,
    ...readHistory(projectId).filter((item) => item.id !== conversation.id),
  ].slice(0, MAX_CONVERSATIONS);
  localStorage.setItem(key(projectId), JSON.stringify(next));
  return next;
}

export function clearHistory(projectId: string) {
  localStorage.removeItem(key(projectId));
}

export function removeConversation(id: string, projectId: string) {
  const next = readHistory(projectId).filter((item) => item.id !== id);
  localStorage.setItem(key(projectId), JSON.stringify(next));
  return next;
}
