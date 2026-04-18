"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, useTransition } from "react";

import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const { ready, token, login, signup } = useAuth();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    if (ready && token) {
      router.replace("/dashboard");
    }
  }, [ready, token, router]);

  const handleSubmit = () => {
    setError(null);
    startTransition(async () => {
      try {
        if (mode === "login") {
          await login(email, password);
        } else {
          await signup(name, email, password);
        }
        router.replace("/dashboard");
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "Could not complete authentication.");
      }
    });
  };

  return (
    <main className="auth-shell">
      <section className="auth-side">
        <p className="eyebrow">Exam Preparation Workspace</p>
        <h1>Enter a clean syllabus-driven workspace for notes, practice, evaluation, and revision.</h1>
        <p>
          Sign in once and keep the full preparation loop in one place: subjects, topics, writing, MCQs, flashcards,
          and revision.
        </p>
        <div className="stack">
          <article className="metric-card">
            <span>Evaluation</span>
            <strong>Deterministic marks with LLM extraction only</strong>
          </article>
          <article className="metric-card">
            <span>Structure</span>
            <strong>Exam context, subject tree, topic-first learning</strong>
          </article>
        </div>
      </section>

      <section className="auth-panel">
        <div className="tabs">
          <button className={mode === "login" ? "tab-button active" : "tab-button"} onClick={() => setMode("login")} type="button">
            Login
          </button>
          <button className={mode === "signup" ? "tab-button active" : "tab-button"} onClick={() => setMode("signup")} type="button">
            Signup
          </button>
        </div>

        <div>
          <h2>{mode === "login" ? "Welcome back" : "Create your account"}</h2>
          <p>{mode === "login" ? "Resume your preparation workspace." : "Start with a secure JWT-backed preparation workspace."}</p>
        </div>

        <div className="form-grid">
          {mode === "signup" ? (
            <input className="input-field" onChange={(event) => setName(event.target.value)} placeholder="Full name" value={name} />
          ) : null}
          <input
            className="input-field"
            onChange={(event) => setEmail(event.target.value)}
            placeholder="Email"
            type="email"
            value={email}
          />
          <input
            className="input-field"
            onChange={(event) => setPassword(event.target.value)}
            placeholder="Password"
            type="password"
            value={password}
          />
        </div>

        {error ? <p className="inline-error">{error}</p> : null}

        <button className="primary-button" disabled={isPending} onClick={handleSubmit} type="button">
          {isPending ? "Working..." : mode === "login" ? "Login" : "Create account"}
        </button>
      </section>
    </main>
  );
}
