"use client";

import { EvaluateUPSCData } from "@/lib/types";

type EvaluationPanelProps = {
  evaluation: EvaluateUPSCData;
  idealMinutes: number;
  timeTakenMinutes: number | null;
  onRewrite: () => void;
  onContinue: () => void;
};

function metricPercent(value: number) {
  return `${Math.round(value * 100)}%`;
}

function trendLabel(value: number) {
  if (value > 0) {
    return `You improved by +${Math.round(value)}% in this topic.`;
  }
  if (value < 0) {
    return `Recent performance is down ${Math.abs(Math.round(value))}%.`;
  }
  return "This topic is holding steady.";
}

function confidenceLabel(value: number) {
  if (value >= 0.8) {
    return "High confidence";
  }
  if (value >= 0.55) {
    return "Medium confidence";
  }
  return "Low confidence";
}

function examReadiness(scoreBand: EvaluateUPSCData["evaluation"]["score_band"]) {
  if (scoreBand === "Topper-level" || scoreBand === "Good") {
    return "Ready";
  }
  if (scoreBand === "Average") {
    return "Borderline";
  }
  return "Not Ready";
}

function hardenFeedbackLine(line: string) {
  return line
    .replace(/you could improve/gi, "Missing")
    .replace(/consider adding/gi, "Missing")
    .replace(/try to/gi, "Not addressed")
    .replace(/needs?/gi, "Weak");
}

function topIssue(report: EvaluateUPSCData["evaluation"]) {
  return report.penalty_reasons[0] || report.mistakes[0] || report.top_improvements[0] || "Not addressed: core demand focus.";
}

function decisiveVerdict(report: EvaluateUPSCData["evaluation"]) {
  const issue = topIssue(report).toLowerCase();
  if (report.score_band === "Poor") {
    return `Weak answer. ${hardenFeedbackLine(issue)}`;
  }
  if (report.score_band === "Average") {
    return `Average answer. ${hardenFeedbackLine(issue)}`;
  }
  if (report.score_band === "Good") {
    return `Good answer. ${hardenFeedbackLine(issue)}`;
  }
  return `Ready answer. ${hardenFeedbackLine(issue)}`;
}

export function EvaluationPanel({ evaluation, idealMinutes, timeTakenMinutes, onRewrite, onContinue }: EvaluationPanelProps) {
  const { analysis, evaluation: report, features, scoring } = evaluation;
  const biggestMistake = hardenFeedbackLine(topIssue(report));
  const improvements = report.top_improvements.slice(0, 3).map((item) => hardenFeedbackLine(item));
  const oneFix = improvements[0] || hardenFeedbackLine(report.next_action);
  const readiness = examReadiness(report.score_band);
  const consistentWeakness = report.consistent_weakness ? `You are consistently weak in: ${report.consistent_weakness}` : null;
  const repeating = report.pressure_message ? hardenFeedbackLine(report.pressure_message) : null;

  return (
    <section className="flow-stack">
      <section className="card evaluation-hero">
        <p className="eyebrow">Step 3</p>
        <div className="score-hero">
          <span className="score-value">{report.scaled_score.toFixed(1)}</span>
          <span className="score-max">/ 10</span>
        </div>
        <h2>Examiner Verdict: {decisiveVerdict(report)}</h2>
        <ul className="bullet-list compact">
          <li>Biggest Mistake: {biggestMistake}</li>
          {consistentWeakness ? <li>{consistentWeakness}</li> : null}
          {repeating ? <li>{repeating}</li> : null}
          <li>Exam Readiness: {readiness}</li>
          <li>
            Percentile {report.percentile}% · {report.performance_band}
          </li>
        </ul>
        <div className="pill-row evaluation-pills">
          <span className="pill soft">{report.score_band}</span>
          <span className="pill">{confidenceLabel(report.confidence)}</span>
          <span className="pill soft">
            {timeTakenMinutes ? `${timeTakenMinutes} min taken vs ${idealMinutes} min ideal` : `${idealMinutes} min ideal`}
          </span>
          <span className="pill">Impression {metricPercent(report.impression_score)}</span>
          <span className="pill streak-pill">🔥 {report.streak} day streak</span>
        </div>
      </section>

      <section className="card">
        <div className="metric-strip">
          <article className="metric-card">
            <span>Coverage</span>
            <strong>{metricPercent(report.coverage_score)}</strong>
          </article>
          <article className="metric-card">
            <span>Relevance</span>
            <strong>{metricPercent(report.relevance_score)}</strong>
          </article>
          <article className="metric-card">
            <span>Structure</span>
            <strong>{metricPercent(report.structure_score)}</strong>
          </article>
        </div>

        <div className="mentor-grid">
          <article className="detail-card">
            <h3>Top 3 Fixes</h3>
            <ul className="bullet-list compact warning">
              {improvements.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </article>
          <article className="detail-card">
            <h3>If You Fix ONE Thing</h3>
            <ul className="bullet-list compact warning">
              <li>{oneFix}</li>
            </ul>
          </article>
          <article className="detail-card">
            <h3>Answer Direction</h3>
            <ul className="bullet-list compact">
              {report.ideal_answer_directions.slice(0, 3).map((item) => (
                <li key={item}>{hardenFeedbackLine(item)}</li>
              ))}
            </ul>
          </article>
          <article className="detail-card mentor-action-card">
            <h3>Next Action</h3>
            <ul className="bullet-list compact">
              <li>{hardenFeedbackLine(report.next_action)}</li>
              <li className="hint-text">{hardenFeedbackLine(trendLabel(report.progress_delta))}</li>
            </ul>
          </article>
        </div>

        <div className="panel-actions">
          <button className="secondary-button" onClick={onRewrite} type="button">
            Rewrite Answer
          </button>
          <button className="primary-button" onClick={onContinue} type="button">
            Open Improvement Tools
          </button>
        </div>
      </section>

      <section className="card">
        <details className="details-block">
          <summary>Detailed signals</summary>
          <div className="details-grid">
            <div className="detail-card">
              <h3>Examiner view</h3>
              <ul className="bullet-list compact">
                <li>Relevance: {analysis.relevance}</li>
                <li>Depth: {analysis.depth}</li>
                <li>Thinking: {analysis.thinking}</li>
                <li>Directive: {analysis.directive}</li>
                <li>Structure: {analysis.structure}</li>
              </ul>
            </div>
            <div className="detail-card">
              <h3>Scoring signals</h3>
              <ul className="bullet-list compact">
                <li>Similarity: {metricPercent(report.similarity_score)}</li>
                <li>Efficiency: {metricPercent(report.efficiency_score)}</li>
                <li>Impression: {metricPercent(report.impression_score)}</li>
                <li>Confidence: {metricPercent(report.confidence)}</li>
              </ul>
            </div>
          </div>
          {report.mistakes.length > 0 ? (
            <div className="detail-card">
              <h3>Main gaps</h3>
              <ul className="bullet-list compact warning">
                {report.mistakes.slice(0, 5).map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {report.missing_concepts.length > 0 ? (
            <div className="detail-card">
              <h3>Missing concepts</h3>
              <ul className="bullet-list compact">
                {report.missing_concepts.slice(0, 6).map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {report.applied_caps.length > 0 || report.applied_penalties.length > 0 ? (
            <div className="details-grid">
              {report.applied_caps.length > 0 ? (
                <div className="detail-card">
                  <h3>Applied caps</h3>
                  <ul className="bullet-list compact warning">
                    {report.applied_caps.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {report.applied_penalties.length > 0 ? (
                <div className="detail-card">
                  <h3>Applied penalties</h3>
                  <ul className="bullet-list compact warning">
                    {report.applied_penalties.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>
          ) : null}
          <div className="detail-card">
            <h3>Backend breakdown</h3>
            <ul className="bullet-list compact">
              <li>Content score: {scoring.content_score}</li>
              <li>Depth score: {scoring.depth_score}</li>
              <li>Directive score: {scoring.directive_score}</li>
              <li>Impression score: {scoring.impression_score}</li>
              <li>Ensemble score: {scoring.ensemble_score}</li>
              <li>Raw score: {scoring.raw_score}</li>
              <li>Signal depth: {features.depth_signals.depth_from_signals}</li>
            </ul>
          </div>
        </details>
      </section>
    </section>
  );
}
