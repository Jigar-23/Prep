"use client";

import Link from "next/link";
import { useEffect } from "react";

import { AppShell } from "@/components/app-shell";
import { AuthGuard } from "@/components/auth-guard";
import { useExamContext } from "@/lib/exam-context";
import { useStudyPractice } from "@/lib/hooks";

export default function PracticePage() {
  const { selectedExamId, setSelectedExamId } = useExamContext();
  const { data, loading, error } = useStudyPractice(selectedExamId);

  useEffect(() => {
    if (data?.exam.id && data.exam.id !== selectedExamId) {
      setSelectedExamId(data.exam.id);
    }
  }, [data?.exam.id, selectedExamId, setSelectedExamId]);

  return (
    <AuthGuard>
      <AppShell title="Practice" subtitle="Daily question and mixed practice." examLabel={data?.exam.name ?? null}>
        {loading ? (
          <div className="empty-state">
            <div>
              <h2>Loading practice</h2>
              <p>Preparing today&apos;s question.</p>
            </div>
          </div>
        ) : error || !data ? (
          <div className="empty-state">
            <div>
              <h2>Practice unavailable</h2>
              <p>{error ?? "The practice page could not be loaded."}</p>
            </div>
          </div>
        ) : (
          <div className="tab-card-stack">
            <section className="hero-card compact-hero">
              <p className="eyebrow">Today&apos;s question</p>
              {data.daily_question ? (
                <div className="continue-card">
                  <div>
                    <h2>{data.daily_question.subtopic_name ? data.daily_question.subtopic_name : data.daily_question.topic_name}</h2>
                    <p>{data.daily_question.question}</p>
                    <p className="body-copy">{data.daily_question.reason}</p>
                  </div>
                  <Link
                    className="primary-button"
                    href={
                      data.daily_question.subtopic_id
                        ? `/topic/${data.daily_question.topic_id}/subtopic/${data.daily_question.subtopic_id}`
                        : `/topic/${data.daily_question.topic_id}?question=${encodeURIComponent(data.daily_question.question)}`
                    }
                  >
                    Start
                  </Link>
                </div>
              ) : (
                <p className="muted-block">Pick a weak chapter below and start writing.</p>
              )}
            </section>

            <section className="card">
              <h3>Weak topics</h3>
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
                      <p>{topic.reason}</p>
                    </Link>
                  ))}
                </div>
              ) : (
                <p className="muted-block">Content coming soon.</p>
              )}
            </section>

            <section className="card">
              <h3>Mixed MCQ drill</h3>
              {data.mixed_mcqs.length > 0 ? (
                <div className="tab-card-stack">
                  {data.mixed_mcqs.map((question) => (
                    <article className="detail-card" key={question.id}>
                      <h4>{question.prompt}</h4>
                      <p>{question.explanation_hint}</p>
                      <Link className="secondary-button compact-button" href={`/topic/${question.topic_id}`}>
                        Open topic drill
                      </Link>
                    </article>
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
