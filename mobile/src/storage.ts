import AsyncStorage from "@react-native-async-storage/async-storage";

import { SessionState } from "./types";

const SESSION_KEY = "perp-mobile-session";
const DRAFT_PREFIX = "perp-mobile-topic-draft";

export async function loadSession(): Promise<SessionState | null> {
  const raw = await AsyncStorage.getItem(SESSION_KEY);
  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw) as SessionState;
  } catch {
    return null;
  }
}

export function saveSession(session: SessionState) {
  return AsyncStorage.setItem(SESSION_KEY, JSON.stringify(session));
}

export function clearSession() {
  return AsyncStorage.removeItem(SESSION_KEY);
}

export async function loadDraft(topicId: string): Promise<{ question: string; answer: string; ocrText: string } | null> {
  const raw = await AsyncStorage.getItem(`${DRAFT_PREFIX}:${topicId}`);
  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw) as { question: string; answer: string; ocrText: string };
  } catch {
    return null;
  }
}

export function saveDraft(topicId: string, draft: { question: string; answer: string; ocrText: string }) {
  return AsyncStorage.setItem(`${DRAFT_PREFIX}:${topicId}`, JSON.stringify(draft));
}
