"use client";

import { ChangeEvent, useEffect, useRef } from "react";

type AnswerEditorProps = {
  question: string;
  onQuestionChange: (value: string) => void;
  suggestedQuestions: string[];
  studentAnswer: string;
  onStudentAnswerChange: (value: string) => void;
  ocrText: string;
  onOcrTextChange: (value: string) => void;
  onImageUpload: (event: ChangeEvent<HTMLInputElement>) => void;
  imageAttached: boolean;
  wordCount: number;
  autosaveLabel: string;
  idealMinutes: number;
  inputError: { field: "question" | "answer"; message: string } | null;
  uploadState: "idle" | "loading" | "ready" | "error";
  uploadLabel: string;
  uploadFileName: string | null;
  busy: boolean;
  onBack: () => void;
  onEvaluate: () => void;
};

export function AnswerEditor({
  question,
  onQuestionChange,
  suggestedQuestions,
  studentAnswer,
  onStudentAnswerChange,
  ocrText,
  onOcrTextChange,
  onImageUpload,
  imageAttached,
  wordCount,
  autosaveLabel,
  idealMinutes,
  inputError,
  uploadState,
  uploadLabel,
  uploadFileName,
  busy,
  onBack,
  onEvaluate,
}: AnswerEditorProps) {
  const questionRef = useRef<HTMLTextAreaElement | null>(null);
  const answerRef = useRef<HTMLTextAreaElement | null>(null);
  const questionInvalid = inputError?.field === "question";
  const answerInvalid = inputError?.field === "answer";

  useEffect(() => {
    if (questionInvalid) {
      questionRef.current?.focus();
      return;
    }
    if (answerInvalid) {
      answerRef.current?.focus();
    }
  }, [answerInvalid, questionInvalid]);

  return (
    <section className="card flow-panel">
      <div className="section-stack">
        <div className="section-copy">
          <p className="eyebrow">Step 2</p>
          <h2>Write the answer</h2>
        </div>
        <div className="meta-row">
          <span className="meta-text">{wordCount} words</span>
          <span className="meta-text">{autosaveLabel}</span>
          <span className="meta-text">Ideal time {idealMinutes} min</span>
        </div>
      </div>

      <div className="editor-stack">
        <div className="input-stack question-focus-card">
          <label className="field-label" htmlFor="question">
            Question in focus
          </label>
          <p className="hint-text">Keep the directive exact. Relevance and structure are judged against this prompt.</p>
          <textarea
            aria-invalid={questionInvalid}
            className={questionInvalid ? "text-area question-area invalid-field" : "text-area question-area"}
            id="question"
            onChange={(event) => onQuestionChange(event.target.value)}
            placeholder="Paste the exact mains question."
            ref={questionRef}
            rows={4}
            value={question}
          />
          {questionInvalid ? <p className="inline-error field-error">{inputError?.message}</p> : null}
          <div className="suggestion-row">
            {suggestedQuestions.map((item) => (
              <button className="ghost-chip" key={item} onClick={() => onQuestionChange(item)} type="button">
                {item}
              </button>
            ))}
          </div>
        </div>

        <div className="input-stack">
          <label className="field-label" htmlFor="student-answer">
            Your answer
          </label>
          <textarea
            aria-invalid={answerInvalid}
            autoFocus
            className={answerInvalid ? "text-area answer-area invalid-field" : "text-area answer-area"}
            id="student-answer"
            onChange={(event) => onStudentAnswerChange(event.target.value)}
            placeholder="Write a crisp intro, analytical body, and conclusion."
            ref={answerRef}
            rows={16}
            value={studentAnswer}
          />
          {answerInvalid ? <p className="inline-error field-error">{inputError?.message}</p> : null}
        </div>

        <div className="input-stack">
          <label className="field-label" htmlFor="ocr-text">
            OCR transcript or handwritten extract
          </label>
          <textarea
            className="text-area secondary-area"
            id="ocr-text"
            onChange={(event) => onOcrTextChange(event.target.value)}
            placeholder="Optional: paste OCR output if you already extracted the handwriting."
            rows={6}
            value={ocrText}
          />
        </div>

        <div className="upload-row">
          <label className="secondary-button upload-button">
            Upload handwritten sheet
            <input accept="image/png,image/jpeg,image/webp,image/heic,image/heif" onChange={onImageUpload} type="file" />
          </label>
          <div className="upload-meta">
            <span className={uploadState === "ready" ? "upload-status ready" : uploadState === "error" ? "upload-status error" : "upload-status"}>
              {uploadState === "ready"
                ? "✓ Sheet ready"
                : uploadState === "loading"
                  ? "Reading sheet..."
                  : uploadState === "error"
                    ? "Upload needs attention"
                    : imageAttached
                      ? "Sheet attached"
                      : "Optional upload"}
            </span>
            {uploadFileName ? <span className="meta-text">{uploadFileName}</span> : null}
            <span className="hint-text">{uploadLabel}</span>
          </div>
        </div>
      </div>

      <div className="panel-actions">
        <button className="secondary-button" onClick={onBack} type="button">
          Back to Topic
        </button>
        <button className="primary-button" disabled={busy} onClick={onEvaluate} type="button">
          {busy ? "Evaluating..." : "Evaluate Answer"}
        </button>
      </div>
    </section>
  );
}
