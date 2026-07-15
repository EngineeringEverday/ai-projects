"use client";

/**
 * MerchVault — Dashboard Shell (Sub-Layout)
 * -------------------------------------------
 * The global fintech shell. Marked 'use client' because the whole dashboard
 * tree performs deep in-memory state mutations (document approvals, status
 * overrides, metadata edits) that must persist across tab views.
 *
 * Layout:
 *   • Left-hand navigation tracking every merchant's live status
 *   • Top app bar: persona switcher · global search · notifications widget
 *
 * Both data (MerchantProvider) and navigation (SelectionProvider) state are
 * mounted here so they survive view transitions within /dashboard.
 */

import { useMemo, useState } from "react";
import {
  Bell,
  Check,
  ChevronDown,
  CircleAlert,
  Headset,
  LayoutGrid,
  Search,
  ShieldCheck,
  Users,
} from "lucide-react";
import { Logo } from "@/components/Logo";
import { Badge, Button } from "@/components/ui";
import {
  MerchantProvider,
  useMerchants,
} from "@/context/MerchantContext";
import {
  SelectionProvider,
  useSelection,
} from "@/context/SelectionContext";
import {
  MerchantStatus,
  PERSONAS,
  STATUS_LABEL,
  STATUS_TONE,
  TicketPriority,
  TicketStatus,
} from "@/types/merchant";
import { cn } from "@/lib/utils";

/* ------------------------------------------------------------------ */
/* Left navigation                                                     */
/* ------------------------------------------------------------------ */

function SideNav() {
  const { merchants, tickets } = useMerchants();
  const { selectedId, selectMerchant, view, setView } = useSelection();

  const counts = useMemo(() => {
    const flagged = merchants.filter(
      (m) =>
        m.status === MerchantStatus.PENDING ||
        m.status === MerchantStatus.UNDER_REVIEW ||
        m.status === MerchantStatus.SUSPENDED
    ).length;
    return { total: merchants.length, flagged };
  }, [merchants]);

  const ticketCounts = useMemo(() => {
    const open = tickets.filter(
      (t) => t.status !== TicketStatus.RESOLVED
    ).length;
    const urgent = tickets.filter(
      (t) => t.priority === TicketPriority.URGENT
    ).length;
    return { open, urgent };
  }, [tickets]);

  const helpdeskActive = view === "helpdesk" && selectedId === null;
  const portfolioActive = view === "portfolio" && selectedId === null;

  return (
    <aside className="flex w-64 shrink-0 flex-col border-r border-slate-800 bg-slate-950">
      <div className="flex h-14 items-center border-b border-slate-800 px-4">
        <Logo />
      </div>

      <nav className="px-3 py-4">
        <button
          onClick={() => {
            setView("portfolio");
            selectMerchant(null);
          }}
          className={cn(
            "flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors",
            portfolioActive
              ? "bg-slate-800 text-slate-100"
              : "text-slate-400 hover:bg-slate-900 hover:text-slate-200"
          )}
        >
          <LayoutGrid className="h-4 w-4" />
          Merchant Portfolio
          <span className="ml-auto rounded bg-slate-800 px-1.5 py-0.5 text-xs text-slate-400">
            {counts.total}
          </span>
        </button>

        <button
          onClick={() => {
            setView("helpdesk");
            selectMerchant(null);
          }}
          className={cn(
            "mt-1 flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors",
            helpdeskActive
              ? "bg-slate-800 text-slate-100"
              : "text-slate-400 hover:bg-slate-900 hover:text-slate-200"
          )}
        >
          <Headset className="h-4 w-4" />
          Helpdesk
          <span className="ml-auto flex items-center gap-1">
            {ticketCounts.urgent > 0 && (
              <span className="rounded bg-rose-500/15 px-1.5 py-0.5 text-xs font-medium text-rose-300">
                {ticketCounts.urgent} urgent
              </span>
            )}
            <span className="rounded bg-slate-800 px-1.5 py-0.5 text-xs text-slate-400">
              {ticketCounts.open} open
            </span>
          </span>
        </button>

        <div className="mt-2 flex items-center gap-2.5 rounded-md px-3 py-2 text-sm text-slate-400">
          <ShieldCheck className="h-4 w-4" />
          Compliance Queue
          <span className="ml-auto rounded bg-amber-500/15 px-1.5 py-0.5 text-xs text-amber-300">
            {counts.flagged}
          </span>
        </div>
        <div className="flex items-center gap-2.5 rounded-md px-3 py-2 text-sm text-slate-400">
          <Users className="h-4 w-4" />
          UBO Registry
        </div>
      </nav>

      <div className="px-3">
        <p className="px-3 pb-2 text-xs font-semibold uppercase tracking-wider text-slate-600">
          Live Accounts
        </p>
        <div className="flex flex-col gap-0.5 overflow-y-auto">
          {merchants.map((m) => {
            const tone = STATUS_TONE[m.status];
            const active = selectedId === m.id;
            return (
              <button
                key={m.id}
                onClick={() => selectMerchant(m.id)}
                className={cn(
                  "group flex items-center gap-2.5 rounded-md px-3 py-2 text-left transition-colors",
                  active
                    ? "bg-slate-800"
                    : "hover:bg-slate-900"
                )}
              >
                <span
                  className={cn(
                    "h-2 w-2 shrink-0 rounded-full",
                    tone === "emerald" && "bg-emerald-400",
                    tone === "amber" && "bg-amber-400",
                    tone === "crimson" && "bg-rose-400",
                    tone === "slate" && "bg-slate-400"
                  )}
                />
                <span className="min-w-0 flex-1">
                  <span
                    className={cn(
                      "block truncate text-sm font-medium",
                      active ? "text-slate-100" : "text-slate-300"
                    )}
                  >
                    {m.businessProfile.dba}
                  </span>
                  <span className="block truncate text-xs text-slate-500">
                    {m.id} · {STATUS_LABEL[m.status]}
                  </span>
                </span>
              </button>
            );
          })}
        </div>
      </div>

      <div className="mt-auto border-t border-slate-800 p-4">
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <ShieldCheck className="h-3.5 w-3.5 text-emerald-500" />
          PayForge Compliance Suite
        </div>
        <p className="mt-1 text-xs text-slate-600">v1.0 · Internal Use Only</p>
      </div>
    </aside>
  );
}

/* ------------------------------------------------------------------ */
/* Persona switcher                                                    */
/* ------------------------------------------------------------------ */

function PersonaSwitcher() {
  const { activePersona, setActivePersona } = useMerchants();
  const [open, setOpen] = useState(false);
  const current = PERSONAS.find((p) => p.id === activePersona)!;

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 rounded-md border border-slate-800 bg-slate-900 px-2 py-1.5 hover:bg-slate-800"
      >
        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-sky-500/20 text-xs font-semibold text-sky-300">
          {current.initials}
        </span>
        <span className="hidden text-left sm:block">
          <span className="block text-xs font-medium text-slate-100">
            {current.name}
          </span>
          <span className="block text-[11px] text-slate-500">
            {current.role}
          </span>
        </span>
        <ChevronDown className="h-4 w-4 text-slate-400" />
      </button>

      {open && (
        <>
          <div
            className="fixed inset-0 z-10"
            onClick={() => setOpen(false)}
          />
          <div className="absolute right-0 z-20 mt-2 w-60 overflow-hidden rounded-lg border border-slate-800 bg-slate-900 shadow-xl animate-scale-in">
            <p className="border-b border-slate-800 px-3 py-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
              Switch Persona
            </p>
            {PERSONAS.map((p) => (
              <button
                key={p.id}
                onClick={() => {
                  setActivePersona(p.id);
                  setOpen(false);
                }}
                className="flex w-full items-center gap-2.5 px-3 py-2.5 text-left hover:bg-slate-800"
              >
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-slate-700 text-xs font-semibold text-slate-200">
                  {p.initials}
                </span>
                <span className="flex-1">
                  <span className="block text-sm text-slate-100">{p.name}</span>
                  <span className="block text-xs text-slate-500">{p.role}</span>
                </span>
                {p.id === activePersona && (
                  <Check className="h-4 w-4 text-emerald-400" />
                )}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Notifications widget                                                */
/* ------------------------------------------------------------------ */

function NotificationsWidget() {
  const { merchants } = useMerchants();
  const [open, setOpen] = useState(false);

  const alerts = useMemo(() => {
    const items: { tone: "amber" | "crimson"; text: string }[] = [];
    merchants.forEach((m) => {
      if (m.financialProfile.chargebackBps >= 80) {
        items.push({
          tone: "crimson",
          text: `${m.businessProfile.dba} chargebacks at ${m.financialProfile.chargebackBps} bps`,
        });
      }
      const pending = m.documents.filter(
        (d) => d.status === "PENDING_REVIEW"
      ).length;
      if (pending > 0) {
        items.push({
          tone: "amber",
          text: `${m.businessProfile.dba} has ${pending} document(s) awaiting review`,
        });
      }
    });
    return items;
  }, [merchants]);

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-label="Notifications"
        className="relative rounded-md border border-slate-800 bg-slate-900 p-2 text-slate-300 hover:bg-slate-800"
      >
        <Bell className="h-4 w-4" />
        {alerts.length > 0 && (
          <span className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-rose-500 text-[10px] font-bold text-white">
            {alerts.length}
          </span>
        )}
      </button>

      {open && (
        <>
          <div
            className="fixed inset-0 z-10"
            onClick={() => setOpen(false)}
          />
          <div className="absolute right-0 z-20 mt-2 w-80 overflow-hidden rounded-lg border border-slate-800 bg-slate-900 shadow-xl animate-scale-in">
            <p className="border-b border-slate-800 px-3 py-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
              Risk & Compliance Alerts
            </p>
            <div className="max-h-80 overflow-y-auto">
              {alerts.length === 0 && (
                <p className="px-3 py-6 text-center text-sm text-slate-500">
                  No active alerts.
                </p>
              )}
              {alerts.map((a, i) => (
                <div
                  key={i}
                  className="flex items-start gap-2.5 border-b border-slate-800/60 px-3 py-3 last:border-0"
                >
                  <CircleAlert
                    className={cn(
                      "mt-0.5 h-4 w-4 shrink-0",
                      a.tone === "crimson" ? "text-rose-400" : "text-amber-400"
                    )}
                  />
                  <p className="text-sm text-slate-300">{a.text}</p>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Top app bar                                                         */
/* ------------------------------------------------------------------ */

function TopBar() {
  const { globalSearch, setGlobalSearch, selectMerchant } = useSelection();

  return (
    <header className="flex h-14 items-center gap-4 border-b border-slate-800 bg-slate-950/80 px-5 backdrop-blur">
      <div className="relative flex-1 max-w-md">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
        <input
          value={globalSearch}
          onChange={(e) => {
            setGlobalSearch(e.target.value);
            selectMerchant(null);
          }}
          placeholder="Search merchants, EIN, descriptors, MCC…"
          className="h-9 w-full rounded-md border border-slate-800 bg-slate-900 pl-9 pr-3 text-sm text-slate-100 placeholder:text-slate-500 focus-visible:border-sky-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/30"
        />
      </div>

      <div className="ml-auto flex items-center gap-2.5">
        <Badge tone="emerald" dot>
          Live
        </Badge>
        <NotificationsWidget />
        <PersonaSwitcher />
      </div>
    </header>
  );
}

/* ------------------------------------------------------------------ */
/* Layout export                                                       */
/* ------------------------------------------------------------------ */

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden bg-slate-950">
      <SideNav />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <main className="flex-1 overflow-y-auto">{children}</main>
      </div>
    </div>
  );
}

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <MerchantProvider>
      <SelectionProvider>
        <Shell>{children}</Shell>
      </SelectionProvider>
    </MerchantProvider>
  );
}
