"use client";

import { ReactNode } from "react";

import { AuthProvider } from "@/lib/auth";
import { ExamProvider } from "@/lib/exam-context";

export function Providers({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <ExamProvider>{children}</ExamProvider>
    </AuthProvider>
  );
}
