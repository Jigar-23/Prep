"use client";

import Link from "next/link";
import { useEffect } from "react";

import { AppShell } from "@/components/app-shell";
import { AuthGuard } from "@/components/auth-guard";
import { useExamContext } from "@/lib/exam-context";
import { useStudyDashboard } from "@/lib/hooks";

function trendText(value: number) {
  if (value > 0) {
    return `Up ${Math.round(value)}%`;
  }
  if (value < 0) {
    return `Down ${Math.abs(Math.round(value))}%`;
  }
  return "Stable";
}

export default function DashboardPage() {
  const { selectedExamId, setSelectedExamId } = useExamContext();
  const { data, loading, error, refresh } = useStudyDashboard(selectedExamId);

  useEffect(() => {
    if (data?.selected_exam_id && data.selected_exam_id !== selectedExamId) {
      setSelectedExamId(data.selected_exam_id);
    }
  }, [data?.selected_exam_id, selectedExamId, setSelectedExamId]);

  return (
    <AuthGuard>
      <AppShell
        title="Dashboard"
        subtitle="Open a subject and continue from the syllabus."
        examLabel={data?.exams.find((exam) => exam.id === (selectedExamId ?? data?.selected_exam_id))?.name ?? null}
        actions={
          <div className="inline-controls">
            <select
              className="select-field compact-select"
              disabled={!data}
              onChange={(event) => setSelectedExamId(event.target.value)}
              value={selectedExamId ?? data?.selected_exam_id ?? ""}
            >
              {(data?.exams ?? []).map((exam) => (
                <option key={exam.id} value={exam.id}>
                  {exam.name}
                </option>
              ))}
            </select>
            <button className="secondary-button compact-button" onClick={() => void refresh()} type="button">
              Refresh
            </button>
          </div>
        }
      >
        {loading ? (
          <div className="empty-state">
            <div>
              <h2>Loading dashboard</h2>
              <p>Preparing your subject workspace.</p>
            </div>
          </div>
        ) : error || !data ? (
          <div className="empty-state">
            <div>
              <h2>Dashboard unavailable</h2>
              <p>{error ?? "The dashboard could not be loaded."}</p>
            </div>
          </div>
        ) : (
          <div className="dashboard-layout">
            <section className="hero-card compact-hero">
              <div className="dashboard-summary">
                <article className="metric-card">
                  <span>Streak</span>
                  <strong>{data.summary.streak} day{data.summary.streak === 1 ? "" : "s"}</strong>
                </article>
                <article className="metric-card">
                  <span>Average</span>
                  <strong>{data.summary.average_score.toFixed(1)}/10</strong>
                </article>
                <article className="metric-card">
                  <span>Last score</span>
                  <strong>{data.summary.last_score != null ? `${data.summary.last_score.toFixed(1)}/10` : "No attempts"}</strong>
                </article>
                <article className="metric-card">
                  <span>Trend</span>
                  <strong>{trendText(data.summary.improvement_trend)}</strong>
                </article>
                <article className="metric-card">
                  <span>Your Weakest Area</span>
                  <strong>{data.summary.weakest_area ? data.summary.weakest_area : "—"}</strong>
                </article>
                <article className="metric-card">
                  <span>Most Repeated Mistake</span>
                  <strong>{data.summary.most_repeated_mistake ? data.summary.most_repeated_mistake : "—"}</strong>
                </article>
              </div>

              {data.summary.recommended_action ? (
                <div className="continue-card">
                  <div>
                    <p className="eyebrow">Continue improvement loop</p>
                    <h2>{data.summary.recommended_action.label}</h2>
                    <p>Fix the weakest signal before moving on.</p>
                  </div>
                  <Link className="primary-button" href={data.summary.recommended_action.href}>
                    Continue
                  </Link>
                </div>
              ) : data.continue_target ? (
                <div className="continue-card">
                  <div>
                    <p className="eyebrow">Continue where you left</p>
                    <h2>{data.continue_target.topic_name}</h2>
                    <p>
                      {data.continue_target.subject_name} · {data.continue_target.reason}
                    </p>
                  </div>
                  <Link className="primary-button" href={data.continue_target.href}>
                    Continue
                  </Link>
                </div>
              ) : null}
            </section>

            <section className="subject-grid">
              {data.subjects.map((subject) => (
                <Link className="subject-card" href={subject.href} key={subject.id}>
                  <div className="subject-card-header">
                    <div>
                      <p className="eyebrow">{subject.code}</p>
                      <h3>{subject.name}</h3>
                    </div>
                    <span className="pill">{subject.topic_count} topics</span>
                  </div>
                  <p>{subject.description}</p>
                  <div className="subject-card-meta">
                    <span>{subject.progress_average_score ? `${subject.progress_average_score.toFixed(1)}/10 avg` : "Fresh start"}</span>
                    <span>{subject.progress_trend ? trendText(subject.progress_trend) : "No trend yet"}</span>
                  </div>
                </Link>
              ))}
            </section>
          </div>
        )}
      </AppShell>
    </AuthGuard>
  );
}
