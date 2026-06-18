import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Processing Platform",
  description: "Upload audio, get a transcript and summary.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="mx-auto flex min-h-screen max-w-3xl flex-col px-4 py-10">
          <header className="mb-8 flex items-center justify-between">
            <a href="/" className="text-base font-semibold text-slate-900">
              AI Processing Platform
            </a>
            <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600">
              {process.env.NEXT_PUBLIC_APP_ENV ?? "dev"}
            </span>
          </header>
          <main className="flex-1">{children}</main>
          <footer className="mt-12 text-center text-xs text-slate-400">
            audio → STT → LLM summary
          </footer>
        </div>
      </body>
    </html>
  );
}
