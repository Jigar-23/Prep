"use client";

import { createContext, ReactNode, useContext, useEffect, useMemo, useState } from "react";

import { readStorage, writeStorage } from "@/lib/storage";

type ExamContextValue = {
  selectedExamId: string | null;
  setSelectedExamId: (value: string) => void;
};

const EXAM_KEY = "prep-selected-exam";
const LEGACY_EXAM_KEY = "perp-selected-exam";
const ExamContext = createContext<ExamContextValue | null>(null);

export function ExamProvider({ children }: { children: ReactNode }) {
  const [selectedExamId, setSelectedExamIdState] = useState<string | null>(null);

  useEffect(() => {
    const saved = readStorage<string>(EXAM_KEY) ?? readStorage<string>(LEGACY_EXAM_KEY);
    if (saved) {
      setSelectedExamIdState(saved);
    }
  }, []);

  const value = useMemo<ExamContextValue>(
    () => ({
      selectedExamId,
      setSelectedExamId: (value: string) => {
        setSelectedExamIdState(value);
        writeStorage(EXAM_KEY, value);
      },
    }),
    [selectedExamId],
  );

  return <ExamContext.Provider value={value}>{children}</ExamContext.Provider>;
}

export function useExamContext() {
  const context = useContext(ExamContext);
  if (!context) {
    throw new Error("useExamContext must be used within ExamProvider");
  }
  return context;
}
