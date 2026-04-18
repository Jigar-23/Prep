import Link from "next/link";

export default function HomePage() {
  return (
    <main className="landing">
      <section className="landing-card">
        <p className="eyebrow">Exam-Driven Preparation System</p>
        <div className="landing-grid">
          <div className="stack">
            <h1>Study from the syllabus, practice inside each topic, and keep revision disciplined.</h1>
            <p>
              Prep is a clean, exam-context-driven preparation workspace. Select the exam, open a subject, move into a
              topic, and use notes, writing, MCQs, flashcards, and revision without page chaos.
            </p>
            <div className="landing-actions">
              <Link className="primary-button" href="/login">
                Open workspace
              </Link>
              <Link className="secondary-button" href="/dashboard">
                Go to dashboard
              </Link>
            </div>
          </div>

          <div className="stack">
            <article className="metric-card">
              <span>Navigation</span>
              <strong>Dashboard, subject, topic, practice, revision.</strong>
            </article>
            <article className="metric-card">
              <span>Learning loop</span>
              <strong>Understand, practice, evaluate, revise, repeat.</strong>
            </article>
            <article className="metric-card">
              <span>Evaluation rule</span>
              <strong>LLM extracts. Backend logic scores.</strong>
            </article>
          </div>
        </div>
      </section>
    </main>
  );
}
