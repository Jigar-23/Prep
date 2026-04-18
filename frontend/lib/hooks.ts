"use client";

import { useEffect, useState } from "react";

import { apiRequest } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  DailyQuestionPayload,
  EvaluateRequest,
  EvaluateUPSCData,
  Exam,
  FlashcardPayload,
  NotesPayload,
  OCRPreviewData,
  RevisionSummaryPayload,
  ReviewCardsData,
  StudyDashboardData,
  StudyMCQAttemptData,
  StudyPracticeData,
  StudyRevisionData,
  StudySubjectData,
  StudyTopicData,
  SubtopicNotesPayload,
  UpdateProgressData,
} from "@/lib/types";

type ResourceState<T> = {
  data: T | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
};

function useProtectedResource<T>(loader: (token: string) => Promise<T>, deps: ReadonlyArray<unknown>): ResourceState<T> {
  const { ready, token } = useAuth();
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    if (!token) {
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const result = await loader(token);
      setData(result);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (ready && token) {
      void load();
      return;
    }
    if (ready) {
      setLoading(false);
    }
  }, [ready, token, ...deps]);

  return { data, loading, error, refresh: load };
}

export function useCatalog(examId?: string | null): ResourceState<Exam[]> {
  return useProtectedResource(
    (token) =>
      apiRequest<{ exams: Exam[] }>(`/catalog/tree${examId ? `?exam_id=${encodeURIComponent(examId)}` : ""}`, { token }).then(
        (result) => result.exams,
      ),
    [examId],
  );
}

export function useDailyQuestion(examId?: string | null): ResourceState<DailyQuestionPayload> {
  return useProtectedResource(
    (token) =>
      apiRequest<{ daily_question: DailyQuestionPayload }>(
        `/daily-question${examId ? `?exam_id=${encodeURIComponent(examId)}` : ""}`,
        { token },
      ).then((result) => result.daily_question),
    [examId],
  );
}

export function useReviewCards(limit = 20): ResourceState<ReviewCardsData> {
  return useProtectedResource(
    (token) => apiRequest<ReviewCardsData>(`/review-cards?limit=${limit}`, { token }),
    [limit],
  );
}

export function useStudyDashboard(examId?: string | null): ResourceState<StudyDashboardData> {
  return useProtectedResource(
    (token) => apiRequest<StudyDashboardData>(`/study/dashboard${examId ? `?exam_id=${encodeURIComponent(examId)}` : ""}`, { token }),
    [examId],
  );
}

export function useStudySubject(subjectId: string, examId?: string | null): ResourceState<StudySubjectData> {
  return useProtectedResource(
    (token) =>
      apiRequest<StudySubjectData>(
        `/study/subject/${subjectId}${examId ? `?exam_id=${encodeURIComponent(examId)}` : ""}`,
        { token },
      ),
    [subjectId, examId],
  );
}

export function useStudyTopic(topicId: string): ResourceState<StudyTopicData> {
  return useProtectedResource((token) => apiRequest<StudyTopicData>(`/study/topic/${topicId}`, { token }), [topicId]);
}

export function useSubtopicNotes(subtopicId: string | null): ResourceState<SubtopicNotesPayload> {
  return useProtectedResource(
    (token) =>
      apiRequest<SubtopicNotesPayload>(`/study/subtopic/${encodeURIComponent(String(subtopicId))}/notes`, { token }),
    [subtopicId],
  );
}

export function useStudyPractice(examId?: string | null): ResourceState<StudyPracticeData> {
  return useProtectedResource(
    (token) => apiRequest<StudyPracticeData>(`/study/practice${examId ? `?exam_id=${encodeURIComponent(examId)}` : ""}`, { token }),
    [examId],
  );
}

export function useStudyRevision(examId?: string | null): ResourceState<StudyRevisionData> {
  return useProtectedResource(
    (token) => apiRequest<StudyRevisionData>(`/study/revision${examId ? `?exam_id=${encodeURIComponent(examId)}` : ""}`, { token }),
    [examId],
  );
}

export async function generateNotes(token: string, topicId: string): Promise<NotesPayload> {
  const result = await apiRequest<{ notes: NotesPayload }>("/generate-notes", {
    method: "POST",
    token,
    body: { topic_id: topicId },
  });

  return result.notes;
}

export async function generateFlashcards(
  token: string,
  topicId: string,
): Promise<{ flashcards: FlashcardPayload[]; revision: RevisionSummaryPayload }> {
  const result = await apiRequest<{ flashcards: FlashcardPayload[]; revision: RevisionSummaryPayload }>("/generate-flashcards", {
    method: "POST",
    token,
    body: { topic_id: topicId },
  });

  return result;
}

export async function evaluateAnswer(token: string, payload: EvaluateRequest): Promise<EvaluateUPSCData> {
  return apiRequest<EvaluateUPSCData>("/evaluate", {
    method: "POST",
    token,
    body: payload,
  });
}

export async function updateReviewProgress(
  token: string,
  cardId: string,
  correct: boolean,
): Promise<UpdateProgressData> {
  return apiRequest<UpdateProgressData>("/update-progress", {
    method: "POST",
    token,
    body: { card_id: cardId, correct },
  });
}

export async function previewOCR(
  token: string,
  payload: { answer_text?: string; handwritten_image_base64?: string; handwritten_image_mime_type?: string },
): Promise<OCRPreviewData> {
  return apiRequest<OCRPreviewData>("/study/ocr-preview", {
    method: "POST",
    token,
    body: payload,
  });
}

export async function submitMCQAttempt(
  token: string,
  payload: { exam_id: string; subject_id: string; topic_id: string; question_id: string; selected_option: string },
): Promise<StudyMCQAttemptData> {
  return apiRequest<StudyMCQAttemptData>("/study/mcq-attempt", {
    method: "POST",
    token,
    body: payload,
  });
}
