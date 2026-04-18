"use client";

type TopicOverviewProps = {
  subjectName: string;
  topicName: string;
  description: string;
  difficulty: string;
  estimatedMinutes: number;
  practiceCounts: {
    mcq: number;
    mains: number;
  };
  focusPoints: string[];
  onStart: () => void;
};

export function TopicOverview({
  subjectName,
  topicName,
  description,
  difficulty,
  estimatedMinutes,
  practiceCounts,
  focusPoints,
  onStart,
}: TopicOverviewProps) {
  return (
    <section className="card flow-panel">
      <div className="section-stack">
        <div className="section-copy">
          <p className="eyebrow">{subjectName}</p>
          <h2>{topicName}</h2>
          <p>{description}</p>
        </div>
        <div className="pill-row">
          <span className="pill">{difficulty}</span>
          <span className="pill soft">{estimatedMinutes} min focus block</span>
          <span className="pill">{practiceCounts.mcq} MCQs</span>
          <span className="pill soft">{practiceCounts.mains} mains prompt</span>
        </div>
      </div>

      <div className="card-grid compact-grid">
        <article className="mini-card">
          <span className="mini-label">Focus Areas</span>
          <ul className="bullet-list compact">
            {focusPoints.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </article>
        <article className="mini-card">
          <span className="mini-label">Workflow</span>
          <ul className="bullet-list compact">
            <li>Write one focused mains answer.</li>
            <li>Run {practiceCounts.mcq} MCQ checks.</li>
            <li>Read structured examiner feedback.</li>
            <li>Open notes and flashcards.</li>
          </ul>
        </article>
      </div>

      <div className="panel-actions">
        <button className="primary-button" onClick={onStart} type="button">
          Start Answer Writing
        </button>
      </div>
    </section>
  );
}
