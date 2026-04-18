"use client";

import Link from "next/link";

import { FlashcardPayload, NotesPayload, RevisionSummaryPayload } from "@/lib/types";

type ImprovementPanelProps = {
  notes: NotesPayload | null;
  flashcards: FlashcardPayload[];
  revision: RevisionSummaryPayload | null;
  busyAction: "notes" | "flashcards" | "evaluate" | null;
  error: string | null;
  onGenerateNotes: () => void;
  onGenerateFlashcards: () => void;
};

export function ImprovementPanel({
  notes,
  flashcards,
  revision,
  busyAction,
  error,
  onGenerateNotes,
  onGenerateFlashcards,
}: ImprovementPanelProps) {
  return (
    <section className="flow-stack">
      <section className="card flow-panel">
        <div className="section-stack">
          <div className="section-copy">
            <p className="eyebrow">Step 4</p>
            <h2>Improvement tools</h2>
            <p>Unlock targeted rebuild assets only after the answer has been evaluated.</p>
          </div>
          <div className="panel-actions">
            <button className="secondary-button" disabled={busyAction !== null} onClick={onGenerateNotes} type="button">
              {busyAction === "notes" ? "Loading notes..." : notes ? "Refresh Notes" : "Generate Notes"}
            </button>
            <button className="primary-button" disabled={busyAction !== null} onClick={onGenerateFlashcards} type="button">
              {busyAction === "flashcards" ? "Loading flashcards..." : flashcards.length ? "Refresh Flashcards" : "Generate Flashcards"}
            </button>
            <Link className="secondary-button" href="/review">
              Go to Revision
            </Link>
          </div>
        </div>
        {error ? <p className="inline-error">{error}</p> : null}
      </section>

      <section className="card">
        <div className="section-stack">
          <div className="section-copy">
            <p className="eyebrow">Notes Engine</p>
            <h2>Exam-ready topic sheet</h2>
          </div>
        </div>
        {notes ? (
          <div className="details-grid">
            <article className="detail-card">
              <h3>30-second revision</h3>
              <ul className="bullet-list compact">
                {notes.thirty_second_revision.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </article>
            <article className="detail-card">
              <h3>Core facts</h3>
              <ul className="bullet-list compact">
                {notes.core_facts.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </article>
            <article className="detail-card">
              <h3>Case laws and value addition</h3>
              <ul className="bullet-list compact">
                {notes.case_laws.slice(0, 4).map((item) => (
                  <li key={item}>{item}</li>
                ))}
                {notes.value_addition.slice(0, 3).map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </article>
            <article className="detail-card">
              <h3>Prelims and mains</h3>
              <ul className="bullet-list compact">
                {notes.prelim_traps.slice(0, 3).map((item) => (
                  <li key={item}>{item}</li>
                ))}
                {notes.pyq.slice(0, 2).map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </article>
          </div>
        ) : (
          <p className="hint-text">Generate notes to build a compact revision sheet for this topic.</p>
        )}
      </section>

      <section className="card">
        <div className="section-stack">
          <div className="section-copy">
            <p className="eyebrow">Step 5</p>
            <h2>Revision queue</h2>
            <p>Convert the topic into active-recall prompts and feed the daily review loop.</p>
          </div>
          {revision ? (
            <div className="pill-row">
              <span className="pill">{revision.cards_added} cards</span>
              <span className="pill soft">{revision.due_today} due today</span>
            </div>
          ) : null}
        </div>
        {flashcards.length > 0 ? (
          <div className="details-grid">
            {flashcards.slice(0, 6).map((card) => (
              <article className="detail-card" key={card.id}>
                <span className="pill">{card.card_type}</span>
                <h3>{card.front}</h3>
                <p>{card.back}</p>
              </article>
            ))}
          </div>
        ) : (
          <p className="hint-text">Generate flashcards to seed spaced repetition for this topic.</p>
        )}
      </section>
    </section>
  );
}
