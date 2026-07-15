"use client";

import { useEffect } from "react";

export default function Home() {
  useEffect(() => {
    // Relative redirect so it works at the domain root and behind any path prefix.
    const base = window.location.href.replace(/\/index\.html?$/, "/").replace(/\/$/, "");
    window.location.replace(`${base}/dashboard.html`);
  }, []);

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-950 text-slate-400">
      <div className="flex items-center gap-3 text-sm">
        <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-400" />
        Loading MerchVault…
      </div>
    </main>
  );
}
