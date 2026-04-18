"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ReactNode } from "react";

import { useAuth } from "@/lib/auth";

type AppShellProps = {
  title: string;
  subtitle?: string;
  children: ReactNode;
  actions?: ReactNode;
  examLabel?: string | null;
};

const navItems = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/practice", label: "Practice" },
  { href: "/revision", label: "Revision" },
];

export function AppShell({ title, subtitle, children, actions, examLabel }: AppShellProps) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();
  const headerMeta = [examLabel, subtitle].filter(Boolean).join(" · ");

  return (
    <div className="app-shell">
      <header className="shell-header">
        <div className="shell-bar minimal-shell-bar">
          <Link className="shell-brand compact-brand" href="/dashboard">
            <span className="brand-mark">Prep</span>
            <div className="brand-copy">
              <strong>Exam workspace</strong>
            </div>
          </Link>

          <nav className="shell-nav">
            {navItems.map((item) => {
              const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
              return (
                <Link key={item.href} href={item.href} className={active ? "nav-link active" : "nav-link"}>
                  {item.label}
                </Link>
              );
            })}
          </nav>

          <div className="shell-user shell-user-compact">
            <div>
              <strong>{user?.name}</strong>
              <p>{user?.email}</p>
            </div>
            <button
              className="secondary-button compact-button"
              onClick={() => {
                logout();
                router.replace("/login");
              }}
              type="button"
            >
              Logout
            </button>
          </div>
        </div>

        <div className="page-header compact-page-header">
          <div className="page-header-copy">
            <h1>{title}</h1>
            {headerMeta ? <p>{headerMeta}</p> : null}
          </div>
          {actions ? <div className="page-actions">{actions}</div> : null}
        </div>
      </header>
      <main className="shell-main">{children}</main>
    </div>
  );
}
