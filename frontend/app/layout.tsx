import type { Metadata } from "next";
import { ReactNode } from "react";

import { Providers } from "@/app/providers";
import "@/app/globals.css";

export const metadata: Metadata = {
  title: "Prep UPSC AI Platform",
  description: "Production-grade UPSC evaluation, notes, flashcard, and revision platform built with Next.js and FastAPI.",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
