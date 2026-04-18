import { Platform } from "react-native";

import {
  AuthData,
  DailyQuestionPayload,
  EvaluateUPSCData,
  Exam,
  FlashcardPayload,
  NotesPayload,
  RevisionSummaryPayload,
  ReviewCardPayload,
  ReviewCardsData,
} from "./types";

const API_BASE_URL =
  process.env.EXPO_PUBLIC_API_BASE_URL ??
  (Platform.OS === "android" ? "http://10.0.2.2:8000" : "http://127.0.0.1:8000");

export class ApiError extends Error {
  code: string;
  status: number;

  constructor(message: string, code: string, status: number) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

async function request<T>(path: string, options: { method?: "GET" | "POST"; token?: string; body?: unknown } = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: options.method ?? "GET",
      headers: {
        "Content-Type": "application/json",
        ...(options.token ? { Authorization: `Bearer ${options.token}` } : {}),
      },
      body: options.body ? JSON.stringify(options.body) : undefined,
    });
  } catch (caught) {
    throw new ApiError(
      caught instanceof Error ? `Could not reach the API: ${caught.message}` : "Could not reach the API.",
      "NETWORK_ERROR",
      0,
    );
  }

  let payload:
    | {
        ok: boolean;
        data?: T;
        error?: { code: string; message: string };
      }
    | null = null;
  try {
    payload = (await response.json()) as {
      ok: boolean;
      data?: T;
      error?: { code: string; message: string };
    };
  } catch {
    const rawText = await response.text();
    throw new ApiError(rawText || `Unexpected API response with status ${response.status}.`, "INVALID_RESPONSE", response.status);
  }

  if (!response.ok || !payload.ok || !payload.data) {
    throw new ApiError(payload.error?.message ?? "Request failed.", payload.error?.code ?? "REQUEST_FAILED", response.status);
  }

  return payload.data;
}

export const api = {
  login(email: string, password: string) {
    return request<AuthData>("/auth/login", {
      method: "POST",
      body: { email, password },
    });
  },

  signup(name: string, email: string, password: string) {
    return request<AuthData>("/auth/signup", {
      method: "POST",
      body: { name, email, password },
    });
  },

  catalog(token: string) {
    return request<{ exams: Exam[] }>("/catalog/tree", { token });
  },

  dailyQuestion(token: string) {
    return request<{ daily_question: DailyQuestionPayload }>("/daily-question", { token });
  },

  generateNotes(token: string, topicId: string) {
    return request<{ notes: NotesPayload }>("/generate-notes", {
      method: "POST",
      token,
      body: { topic_id: topicId },
    });
  },

  generateFlashcards(token: string, topicId: string) {
    return request<{ flashcards: FlashcardPayload[]; revision: RevisionSummaryPayload }>("/generate-flashcards", {
      method: "POST",
      token,
      body: { topic_id: topicId },
    });
  },

  evaluate(
    token: string,
    payload: {
      topic_id: string;
      subtopic_id?: string;
      question: string;
      student_answer?: string;
      ocr_text?: string;
      handwritten_image_base64?: string;
      handwritten_image_mime_type?: string;
      max_marks?: number;
      include_learning_assets?: boolean;
    },
  ) {
    return request<EvaluateUPSCData>("/evaluate", {
      method: "POST",
      token,
      body: payload,
    });
  },

  reviewCards(token: string, limit = 20) {
    return request<ReviewCardsData>(`/review-cards?limit=${limit}`, { token });
  },

  updateProgress(token: string, cardId: string, correct: boolean) {
    return request<{ progress: ReviewCardPayload["progress"]; revision: RevisionSummaryPayload }>("/update-progress", {
      method: "POST",
      token,
      body: { card_id: cardId, correct },
    });
  },
};
