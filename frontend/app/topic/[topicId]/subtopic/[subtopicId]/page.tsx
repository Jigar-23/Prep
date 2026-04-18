"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useMemo, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { AuthGuard } from "@/components/auth-guard";
import { EvaluationPanel } from "@/components/EvaluationPanel";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { evaluateAnswer, useStudyTopic, useSubtopicNotes } from "@/lib/hooks";
import { EvaluateUPSCData } from "@/lib/types";

const MIN_ANSWER_LENGTH = 20;

export default function SubtopicNotesPage() {
  const params = useParams<{ topicId: string; subtopicId: string }>();
  const topicId = Array.isArray(params.topicId) ? params.topicId[0] : params.topicId;
  const subtopicId = Array.isArray(params.subtopicId) ? params.subtopicId[0] : params.subtopicId;

  const { token } = useAuth();
  const { data: chapterData } = useStudyTopic(topicId);
  const { data, loading, error } = useSubtopicNotes(subtopicId);

  const [answerText, setAnswerText] = useState("");
  const [answerError, setAnswerError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [evaluation, setEvaluation] = useState<EvaluateUPSCData | null>(null);
  const [pageError, setPageError] = useState<string | null>(null);

  const subtopicTitle = useMemo(() => {
    const sections = chapterData?.sections ?? [];
    for (const section of sections) {
      for (const item of section.items) {
        if (item.id === subtopicId) return item.title;
      }
    }
    return "Subtopic";
  }, [chapterData?.sections, subtopicId]);

  const prompt = useMemo(() => {
    return `Write a 150-word UPSC mains answer on: ${subtopicTitle}.`;
  }, [subtopicTitle]);

  const submit = async () => {
    if (!token) return;
    if (answerText.trim().length < MIN_ANSWER_LENGTH) {
      setAnswerError("Write at least 20 clear characters before submitting.");
      return;
    }
    setBusy(true);
    setPageError(null);
    setAnswerError(null);
    try {
      const result = await evaluateAnswer(token, {
        topic_id: topicId,
        subtopic_id: subtopicId,
        question: prompt,
        student_answer: answerText.trim(),
        max_marks: 10,
        include_learning_assets: false,
      });
      setEvaluation(result);
    } catch (caught) {
      if (caught instanceof ApiError && caught.errorType === "INPUT_INVALID") {
        setAnswerError("We couldn’t process your answer. Write cleanly and retry.");
      } else {
        setPageError(caught instanceof Error ? caught.message : "Could not evaluate the answer.");
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthGuard>
      <AppShell
        title={subtopicTitle}
        subtitle={chapterData?.topic?.name ?? "Chapter"}
        examLabel={chapterData?.exam?.name ?? null}
        actions={
          <Link className="secondary-button compact-button" href={`/topic/${encodeURIComponent(topicId)}`}>
            Back to chapter
          </Link>
        }
      >
        {loading ? (
          <div className="empty-state">
            <div>
              <h2>Loading notes</h2>
              <p>Generating exam-ready framework.</p>
            </div>
          </div>
        ) : error || !data ? (
          <div className="empty-state">
            <div>
              <h2>Notes unavailable</h2>
              <p>{error ?? "The notes could not be loaded."}</p>
            </div>
          </div>
        ) : (
          <div className="topic-layout">
            {pageError ? <p className="inline-error">{pageError}</p> : null}

            <div className="tab-card-stack">
              <article className="card">
                <h3>Quick recall</h3>
                <ul className="bullet-list compact">
                  {data.quick_recall.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </article>

              <article className="card">
                <h3>Structured answer framework</h3>
                <div className="notes-grid">
                  {Object.entries(data.structured_answer_framework ?? {}).map(([key, value]) => (
                    <div className="detail-card" key={key}>
                      <h4>{key}</h4>
                      <ul className="bullet-list compact">
                        {(Array.isArray(value) ? value : []).map((v) => (
                          <li key={String(v)}>{String(v)}</li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              </article>

              <article className="card">
                <h3>150-word ready answer</h3>
                <p>{data.ready_answer_150}</p>
              </article>

              <article className="card">
                <h3>Key facts / examples</h3>
                <ul className="bullet-list compact">
                  {data.key_facts_examples.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </article>

              <article className="card">
                <h3>Value addition</h3>
                <ul className="bullet-list compact">
                  {data.value_addition.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </article>

              <article className="card">
                <h3>Diagram / flow</h3>
                <ul className="bullet-list compact">
                  {data.diagram_flow.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </article>

              <article className="card answer-workspace">
                <div className="subject-card-header">
                  <div>
                    <h3>Apply now</h3>
                    <p>Write 150 words. Get evaluated. Fix the weakest dimension.</p>
                  </div>
                  <span className="pill soft">150 words</span>
                </div>
                <div className="question-highlight">
                  <p className="eyebrow">Prompt</p>
                  <h3>{prompt}</h3>
                </div>
                <textarea
                  className={answerError ? "text-area answer-area invalid-field" : "text-area answer-area"}
                  onChange={(event) => setAnswerText(event.target.value)}
                  placeholder="Write the answer."
                  rows={12}
                  value={answerText}
                />
                {answerError ? <p className="inline-error field-error">{answerError}</p> : null}
                <div className="panel-actions">
                  <button className="primary-button" disabled={busy} onClick={() => void submit()} type="button">
                    {busy ? "Evaluating..." : "Evaluate answer"}
                  </button>
                  <button
                    className="secondary-button"
                    onClick={() => {
                      setAnswerText("");
                      setEvaluation(null);
                      setAnswerError(null);
                      setPageError(null);
                    }}
                    type="button"
                  >
                    Reset
                  </button>
                </div>
              </article>

              {evaluation ? (
                <EvaluationPanel
                  evaluation={evaluation}
                  idealMinutes={chapterData?.topic?.estimated_minutes ?? 20}
                  onContinue={() => {
                    // If pressure loop hit, UI already says retry; keep user here.
                    if (evaluation.evaluation.pressure_message) return;
                    window.location.href = `/topic/${encodeURIComponent(topicId)}`;
                  }}
                  onRewrite={() => {
                    setEvaluation(null);
                  }}
                  timeTakenMinutes={null}
                />
              ) : null}
            </div>
          </div>
        )}
      </AppShell>
    </AuthGuard>
  );
}

