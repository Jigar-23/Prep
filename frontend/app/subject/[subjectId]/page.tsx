"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { AuthGuard } from "@/components/auth-guard";
import { useExamContext } from "@/lib/exam-context";
import { useStudySubject } from "@/lib/hooks";
import { SubjectTopicPreviewPayload } from "@/lib/types";

type SubjectTab = "notes" | "questions" | "mcqs" | "progress";

export default function SubjectPage() {
  const params = useParams<{ subjectId: string }>();
  const subjectId = Array.isArray(params.subjectId) ? params.subjectId[0] : params.subjectId;
  const { selectedExamId, setSelectedExamId } = useExamContext();
  const { data, loading, error } = useStudySubject(subjectId, selectedExamId);
  const [activeTab, setActiveTab] = useState<SubjectTab>("notes");
  const [selectedTopicId, setSelectedTopicId] = useState<string | null>(null);

  useEffect(() => {
    if (data?.exam.id && data.exam.id !== selectedExamId) {
      setSelectedExamId(data.exam.id);
    }
  }, [data?.exam.id, selectedExamId, setSelectedExamId]);

  useEffect(() => {
    if (!selectedTopicId && data?.syllabus[0]?.id) {
      setSelectedTopicId(data.syllabus[0].id);
    }
  }, [data?.syllabus, selectedTopicId]);

  const selectedTopic = useMemo(
    () => data?.syllabus.find((topic) => topic.id === selectedTopicId) ?? data?.syllabus[0],
    [data?.syllabus, selectedTopicId],
  );

  const renderPreviewCards = (items: SubjectTopicPreviewPayload[], mode: SubjectTab) => {
    if (!items.length) {
      return <p className="muted-block">Content coming soon.</p>;
    }
    return (
      <div className="tab-card-stack">
        {items.map((item) => (
          <article className="card subject-preview-card" key={`${mode}-${item.topic_id}`}>
            <div className="subject-card-header">
              <div>
                <h3>{item.topic_name}</h3>
                <p>{item.description}</p>
              </div>
              <Link className="secondary-button compact-button" href={`/topic/${item.topic_id}`}>
                Open topic
              </Link>
            </div>
            {mode === "notes" ? <p className="body-copy">{item.note_preview}</p> : null}
            <div className="pill-row">
              <span className="pill">{item.mcq_count} MCQs</span>
              <span className="pill soft">{item.practice_count} practice</span>
              <span className="pill soft">{item.pyq_count} PYQs</span>
              <span className="pill">{item.note_ready ? "Notes ready" : "Notes coming soon"}</span>
            </div>
          </article>
        ))}
      </div>
    );
  };

  return (
    <AuthGuard>
      <AppShell
        title={data?.subject.name ?? "Subject"}
        subtitle={data?.subject.description ?? "Syllabus-driven subject workspace."}
        examLabel={data?.exam.name ?? null}
        actions={
          selectedTopic ? (
            <Link className="primary-button" href={`/topic/${selectedTopic.id}`}>
              Open {selectedTopic.name}
            </Link>
          ) : null
        }
      >
        {loading ? (
          <div className="empty-state">
            <div>
              <h2>Loading subject</h2>
              <p>Building the syllabus view and topic content map.</p>
            </div>
          </div>
        ) : error || !data ? (
          <div className="empty-state">
            <div>
              <h2>Subject unavailable</h2>
              <p>{error ?? "The selected subject could not be loaded."}</p>
            </div>
          </div>
        ) : (
          <div className="subject-layout">
            <aside className="syllabus-panel">
              <div className="panel-section">
                <p className="eyebrow">Full syllabus</p>
                <h2>{data.subject.name}</h2>
              </div>
              <div className="syllabus-tree">
                {data.syllabus.map((topic) => (
                  <details className="syllabus-node" key={topic.id} open={selectedTopicId === topic.id}>
                    <summary
                      className={selectedTopicId === topic.id ? "syllabus-summary active" : "syllabus-summary"}
                      onClick={() => setSelectedTopicId(topic.id)}
                    >
                      <span>{topic.name}</span>
                      <span className="pill soft">{topic.estimated_minutes} min</span>
                    </summary>
                    {topic.subtopics && topic.subtopics.length > 0 ? (
                      <ul className="syllabus-subtopics">
                        {topic.subtopics.map((subtopic) => (
                          <li key={subtopic.id}>{subtopic.name}</li>
                        ))}
                      </ul>
                    ) : (
                      <p className="muted-block">Content coming soon.</p>
                    )}
                  </details>
                ))}
              </div>
            </aside>

            <section className="subject-main-panel">
              <div className="tab-row">
                {(["notes", "questions", "mcqs", "progress"] as SubjectTab[]).map((tab) => (
                  <button
                    className={activeTab === tab ? "tab-button active-tab" : "tab-button"}
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    type="button"
                  >
                    {tab === "mcqs" ? "MCQs" : tab[0].toUpperCase() + tab.slice(1)}
                  </button>
                ))}
              </div>

              {activeTab === "notes" ? renderPreviewCards(data.notes_topics, "notes") : null}
              {activeTab === "questions" ? renderPreviewCards(data.question_topics, "questions") : null}
              {activeTab === "mcqs" ? renderPreviewCards(data.mcq_topics, "mcqs") : null}
              {activeTab === "progress" ? (
                <div className="tab-card-stack">
                  <section className="hero-card compact-hero">
                    <div className="dashboard-summary">
                      <article className="metric-card">
                        <span>Average</span>
                        <strong>{data.progress.average_score.toFixed(1)}/10</strong>
                      </article>
                      <article className="metric-card">
                        <span>Attempts</span>
                        <strong>{data.progress.total_attempts}</strong>
                      </article>
                      <article className="metric-card">
                        <span>Due revisions</span>
                        <strong>{data.progress.due_revisions}</strong>
                      </article>
                    </div>
                  </section>
                  <article className="card">
                    <h3>Priority repair areas</h3>
                    {data.progress.weak_topics.length > 0 ? (
                      <ul className="bullet-list compact">
                        {data.progress.weak_topics.map((topic) => (
                          <li key={topic}>{topic}</li>
                        ))}
                      </ul>
                    ) : (
                      <p className="muted-block">Progress data will appear after attempts are recorded.</p>
                    )}
                  </article>
                </div>
              ) : null}
            </section>
          </div>
        )}
      </AppShell>
    </AuthGuard>
  );
}
