"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo } from "react";

import { AppShell } from "@/components/app-shell";
import { AuthGuard } from "@/components/auth-guard";
import { useExamContext } from "@/lib/exam-context";
import { useStudyTopic } from "@/lib/hooks";

function progressPct(done: number, total: number) {
  if (total <= 0) return 0;
  return Math.max(0, Math.min(100, Math.round((done / total) * 100)));
}

function statusDot(status: string) {
  if (status === "done") return "✅";
  if (status === "weak") return "🔴";
  return "⚪";
}

export default function TopicPage() {
  const params = useParams<{ topicId: string }>();
  const topicId = Array.isArray(params.topicId) ? params.topicId[0] : params.topicId;
  const { selectedExamId, setSelectedExamId } = useExamContext();
  const { data, loading, error } = useStudyTopic(topicId);

  useEffect(() => {
    if (data?.exam.id && data.exam.id !== selectedExamId) {
      setSelectedExamId(data.exam.id);
    }
  }, [data?.exam.id, selectedExamId, setSelectedExamId]);

  const chapter = data?.chapter_progress ?? null;
  const pct = useMemo(
    () => progressPct(chapter?.completed_count ?? 0, chapter?.total_subtopics ?? 0),
    [chapter?.completed_count, chapter?.total_subtopics],
  );

  const continueHref =
    chapter?.continue_subtopic_id && data?.topic?.id
      ? `/topic/${encodeURIComponent(data.topic.id)}/subtopic/${encodeURIComponent(chapter.continue_subtopic_id)}`
      : null;

  return (
    <AuthGuard>
      <AppShell
        title={data?.topic.name ?? "Chapter"}
        subtitle={data?.subject.name ?? "Chapter workspace"}
        examLabel={data?.exam.name ?? null}
        actions={<Link className="secondary-button compact-button" href={`/subject/${data?.subject.id ?? ""}`}>Back to subject</Link>}
      >
        {loading ? (
          <div className="empty-state">
            <div>
              <h2>Loading chapter</h2>
              <p>Building subtopics, progress, and next action.</p>
            </div>
          </div>
        ) : error || !data ? (
          <div className="empty-state">
            <div>
              <h2>Chapter unavailable</h2>
              <p>{error ?? "The chapter could not be loaded."}</p>
            </div>
          </div>
        ) : (
          <div className="topic-layout">
            <section className="hero-card question-hero">
              <div className="topic-hero-copy">
                <p className="eyebrow">{data.subject.name}</p>
                <h2>{data.topic.name}</h2>
                <p className="muted-block">{data.topic.description}</p>
              </div>
              <div className="pill-row">
                <span className="pill">{data.topic.difficulty}</span>
                <span className="pill soft">{data.topic.estimated_minutes} min</span>
                <span className="pill">{chapter?.completed_count ?? 0}/{chapter?.total_subtopics ?? 0} done</span>
                <span className="pill soft">{chapter?.weak_count ?? 0} weak</span>
              </div>
            </section>

            <article className="card">
              <div className="subject-card-header">
                <div>
                  <h3>Chapter progress</h3>
                  <p>Complete subtopics. Fix weak ones before moving on.</p>
                </div>
                {continueHref ? (
                  <Link className="primary-button" href={continueHref}>
                    Continue where you left
                  </Link>
                ) : (
                  <span className="pill soft">Start with any subtopic</span>
                )}
              </div>
              <div className="progress-track" aria-label="Chapter progress">
                <div className="progress-fill" style={{ width: `${pct}%` }} />
              </div>
            </article>

            <div className="tab-card-stack">
              {(data.sections ?? []).map((section) => (
                <article className="card" key={section.name}>
                  <div className="subject-card-header">
                    <div>
                      <h3>{section.name}</h3>
                      <p>{section.items.length} subtopics</p>
                    </div>
                  </div>
                  <div className="card-grid">
                    {section.items.map((item) => (
                      <Link
                        className={item.status === "weak" ? "detail-card weak-card" : "detail-card"}
                        href={`/topic/${encodeURIComponent(data.topic.id)}/subtopic/${encodeURIComponent(item.id)}`}
                        key={item.id}
                      >
                        <p className="eyebrow">
                          {statusDot(item.status)} {item.status === "not_started" ? "not started" : item.status}
                        </p>
                        <h4>{item.title}</h4>
                        <p className="muted-block">Open notes → write 150 words → get evaluated.</p>
                      </Link>
                    ))}
                  </div>
                </article>
              ))}
            </div>
          </div>
        )}
      </AppShell>
    </AuthGuard>
  );
}
