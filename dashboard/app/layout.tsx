import "./globals.css";
import type { Metadata } from "next";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "Repo Surgeon",
  description: "Multi-repo GAP agent — live cockpit",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-bg text-zinc-200 antialiased">
        <Providers>
          <div className="border-b border-border bg-panel">
            <div className="max-w-7xl mx-auto px-6 py-3 flex items-center justify-between">
              <div className="flex items-center gap-6">
                <a href="/" className="font-bold tracking-tight">
                  <span className="text-accent">▶</span> repo-surgeon
                </a>
                <nav className="flex gap-4 text-sm text-zinc-400">
                  <a href="/" className="hover:text-zinc-100">Runs</a>
                  <a href="/memory" className="hover:text-zinc-100">Memory</a>
                  <a href="/evals" className="hover:text-zinc-100">Evals</a>
                  <a href="/repos" className="hover:text-zinc-100">Repos</a>
                </nav>
              </div>
              <div className="text-xs text-muted font-mono">localhost:8000</div>
            </div>
          </div>
          <main className="max-w-7xl mx-auto px-6 py-6">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
