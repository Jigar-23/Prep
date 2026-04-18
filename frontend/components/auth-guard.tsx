"use client";

import { ReactNode, useEffect } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/lib/auth";

export function AuthGuard({ children }: { children: ReactNode }) {
  const router = useRouter();
  const { ready, token } = useAuth();

  useEffect(() => {
    if (ready && !token) {
      router.replace("/login");
    }
  }, [ready, token, router]);

  if (!ready || !token) {
    return (
      <div className="empty-state">
        <h2>Loading your workspace</h2>
        <p>We are checking your session and preparing your study dashboard.</p>
      </div>
    );
  }

  return <>{children}</>;
}
