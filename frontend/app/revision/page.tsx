"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { AuthGuard } from "@/components/auth-guard";
import { useAuth } from "@/lib/auth";
import { useExamContext } from "@/lib/exam-context";
import { updateReviewProgress, useStudyRevision } from "@/lib/hooks";

export default function RevisionPage() {
  const { token } = useAuth();
  const { selectedExamId, setSelectedExamId } = useExamContext();
  const { data, loading, error, refresh } = useStudyRevision(selectedExamId);
  const [revealed, setRevealed] = useState<Record<string, boolean>>({});
  const [busyId, setBusyId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    if (data?.exam.id && data.exam.id !== selectedExamId) {
      setSelectedExamId(data.exam.id);
    }
  }, [data?.exam.id, selectedExamId, setSelectedExamId]);

  const handleProgress = async (cardId: string, correct: boolean) => {
    if (!token) {
      return;
    }
    setBusyId(cardId);
    setActionError(null);
    try {
      await updateReviewProgress(token, cardId, correct);
      setRevealed((current) => ({ ...current, [cardId]: false }));
      await refresh();
    } catch (caught) {
      setActionError(caught instanceof Error ? caught.message : "Could not update revision progress.");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <AuthGuard>
      <AppShell title="Revision" subtitle="Due cards and weak topics." examLabel={data?.exam.name ?? null}>
        {loading ? (
          <div className="empty-state">
            <div>
              <h2>Loading revision</h2>
              <p>Preparing revision items.</p>
            </div>
          </div>
        ) : error || !data ? (
          <div className="empty-state">
            <div>
              <h2>Revision unavailable</h2>
              <p>{error ?? "The revision page could not be loaded."}</p>
            </div>
          </div>
        ) : (
          <div className="tab-card-stack">
            <section className="hero-card compact-hero">
              <div className="dashboard-summary">
                <article className="metric-card">
                  <span>Due now</span>
                  <strong>{data.review_cards.length}</strong>
                </article>
                <article className="metric-card">
                  <span>Average</span>
                  <strong>{data.summary.average_score.toFixed(1)}/10</strong>
                </article>
                <article className="metric-card">
                  <span>Streak</span>
                  <strong>{data.summary.streak} days</strong>
                </article>
              </div>
            </section>

            {actionError ? <p className="inline-error">{actionError}</p> : null}

            <section className="tab-card-stack">
              {data.review_cards.length > 0 ? (
                data.review_cards.map((card) => {
                  const isRevealed = Boolean(revealed[card.id]);
                  return (
                    <article className="card" key={card.id}>
                      <div className="subject-card-header">
                        <div>
                          <p className="eyebrow">{card.topic_name}</p>
                          <h3>{card.front}</h3>
                        </div>
                        <span className="pill">{card.card_type}</span>
                      </div>
                      {isRevealed ? (
                        <div className="feedback-box">
                          <p>{card.back}</p>
                          <p className="body-copy">{card.explanation}</p>
                        </div>
                      ) : (
                        <p className="muted-block">Recall first, then reveal.</p>
                      )}
                      <div className="panel-actions">
                        <button
                          className="secondary-button"
                          onClick={() => setRevealed((current) => ({ ...current, [card.id]: !isRevealed }))}
                          type="button"
                        >
                          {isRevealed ? "Hide answer" : "Reveal answer"}
                        </button>
                        <button
                          className="primary-button"
                          disabled={!isRevealed || busyId === card.id}
                          onClick={() => void handleProgress(card.id, true)}
                          type="button"
                        >
                          {busyId === card.id ? "Updating..." : "I recalled this"}
                        </button>
                        <button
                          className="secondary-button"
                          disabled={!isRevealed || busyId === card.id}
                          onClick={() => void handleProgress(card.id, false)}
                          type="button"
                        >
                          I missed this
                        </button>
                      </div>
                    </article>
                  );
                })
              ) : (
                <article className="card">
                  <p className="muted-block">No cards are due right now.</p>
                </article>
              )}
            </section>

            <section className="card">
              <h3>Weak topics to revisit</h3>
              {data.weak_topics.length > 0 ? (
                <div className="subject-grid">
                  {data.weak_topics.map((topic) => (
                    <Link className="subject-card" href={topic.href} key={topic.topic_id}>
                      <div className="subject-card-header">
                        <div>
                          <h3>{topic.topic_name}</h3>
                          <p>{topic.subject_name}</p>
                        </div>
                        {topic.average_score ? <span className="pill">{topic.average_score.toFixed(1)}/10</span> : null}
                      </div>
                      <p>{topic.trend_delta ? `Trend ${topic.trend_delta.toFixed(0)}%` : "Open topic"}</p>
                    </Link>
                  ))}
                </div>
              ) : (
                <p className="muted-block">Content coming soon.</p>
              )}
            </section>
          </div>
        )}
      </AppShell>
    </AuthGuard>
  );
}
