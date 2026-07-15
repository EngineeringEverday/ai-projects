"use client";

/**
 * MerchVault — Portfolio Dashboard (Main View)
 * ----------------------------------------------
 * Global volume metric cards + a dense, sortable, filterable merchant table.
 * The table implements its own column model, sorting, and multi-field filtering
 * (mimicking the ergonomics of TanStack Table without the dependency).
 *
 * When a merchant is selected (from the table or the side-nav), this view swaps
 * to the full MerchantDetailWorkspace.
 */

import { useMemo, useState } from "react";
import {
  ArrowDownUp,
  ArrowLeft,
  ChevronDown,
  ChevronUp,
  CircleDollarSign,
  FileWarning,
  ShieldAlert,
  TrendingUp,
  Wallet,
} from "lucide-react";
import { Badge, Button, Card, CardContent, Select } from "@/components/ui";
import { useMerchants } from "@/context/MerchantContext";
import { useSelection } from "@/context/SelectionContext";
import { MerchantDetailWorkspace } from "@/components/MerchantDetailWorkspace";
import { HelpdeskWorkspace } from "@/components/HelpdeskWorkspace";
import {
  DocStatus,
  Merchant,
  MerchantStatus,
  RISK_LABEL,
  RISK_TONE,
  RiskTier,
  STATUS_LABEL,
  STATUS_TONE,
} from "@/types/merchant";
import { cn, formatCompactUsd } from "@/lib/utils";

/* ------------------------------------------------------------------ */
/* Metric cards                                                        */
/* ------------------------------------------------------------------ */

function MetricCard({
  label,
  value,
  sub,
  icon: Icon,
  tone = "slate",
}: {
  label: string;
  value: string;
  sub: string;
  icon: React.ElementType;
  tone?: "slate" | "emerald" | "amber" | "crimson" | "sky";
}) {
  const ring: Record<string, string> = {
    slate: "text-slate-400 bg-slate-800/60",
    sky: "text-sky-400 bg-sky-500/10",
    emerald: "text-emerald-400 bg-emerald-500/10",
    amber: "text-amber-400 bg-amber-500/10",
    crimson: "text-rose-400 bg-rose-500/10",
  };
  return (
    <Card>
      <CardContent className="flex items-start justify-between p-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
            {label}
          </p>
          <p className="mt-1.5 text-2xl font-semibold tabular-nums text-slate-100">
            {value}
          </p>
          <p className="mt-1 text-xs text-slate-500">{sub}</p>
        </div>
        <span
          className={cn(
            "flex h-9 w-9 items-center justify-center rounded-lg",
            ring[tone]
          )}
        >
          <Icon className="h-4.5 w-4.5" />
        </span>
      </CardContent>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* Sortable table                                                      */
/* ------------------------------------------------------------------ */

type SortKey =
  | "legalName"
  | "riskScore"
  | "monthlyVolumeUsd"
  | "chargebackBps"
  | "status";

interface ColumnDef {
  key: SortKey;
  label: string;
  align?: "left" | "right";
  numeric?: boolean;
}

const COLUMNS: ColumnDef[] = [
  { key: "legalName", label: "Merchant", align: "left" },
  { key: "riskScore", label: "Risk", align: "left" },
  { key: "monthlyVolumeUsd", label: "Monthly Volume", align: "right", numeric: true },
  { key: "chargebackBps", label: "CB (bps)", align: "right", numeric: true },
  { key: "status", label: "Status", align: "left" },
];

function MerchantTable() {
  const { merchants } = useMerchants();
  const { selectMerchant, globalSearch, setGlobalSearch } = useSelection();
  const [sortKey, setSortKey] = useState<SortKey>("riskScore");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [riskFilter, setRiskFilter] = useState<string>("ALL");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");

  const filtered = useMemo(() => {
    const q = globalSearch.trim().toLowerCase();
    let rows = merchants.filter((m) => {
      if (riskFilter !== "ALL" && m.riskTier !== riskFilter) return false;
      if (statusFilter !== "ALL" && m.status !== statusFilter) return false;
      if (!q) return true;
      const haystack = [
        m.legalName,
        m.businessProfile.dba,
        m.id,
        m.businessProfile.ein,
        m.businessProfile.processingDescriptor,
        m.businessProfile.mccCode,
        m.businessProfile.mccDescription,
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(q);
    });

    rows = [...rows].sort((a, b) => {
      const dir = sortDir === "asc" ? 1 : -1;
      const read = (m: Merchant): string | number => {
        switch (sortKey) {
          case "legalName":
            return m.legalName;
          case "riskScore":
            return m.riskScore;
          case "monthlyVolumeUsd":
            return m.financialProfile.monthlyVolumeUsd;
          case "chargebackBps":
            return m.financialProfile.chargebackBps;
          case "status":
            return m.status;
        }
      };
      const av = read(a);
      const bv = read(b);
      if (typeof av === "number" && typeof bv === "number")
        return (av - bv) * dir;
      return String(av).localeCompare(String(bv)) * dir;
    });
    return rows;
  }, [merchants, globalSearch, riskFilter, statusFilter, sortKey, sortDir]);

  const toggleSort = (key: SortKey) => {
    if (key === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  };

  return (
    <Card className="overflow-hidden">
      {/* Filter bar */}
      <div className="flex flex-wrap items-center gap-3 border-b border-slate-800 px-4 py-3">
        <div className="flex items-center gap-1.5 text-sm font-medium text-slate-200">
          <ArrowDownUp className="h-4 w-4 text-slate-500" />
          Merchant Portfolio
          <span className="ml-1 rounded bg-slate-800 px-1.5 py-0.5 text-xs text-slate-400">
            {filtered.length}
          </span>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <div className="w-40">
            <Select
              aria-label="Filter by risk"
              value={riskFilter}
              onChange={(e) => setRiskFilter(e.target.value)}
              options={[
                { value: "ALL", label: "All Risk Tiers" },
                { value: RiskTier.LOW, label: "Low" },
                { value: RiskTier.MEDIUM, label: "Medium" },
                { value: RiskTier.MEDIUM_HIGH, label: "Medium-High" },
                { value: RiskTier.HIGH, label: "High" },
              ]}
            />
          </div>
          <div className="w-40">
            <Select
              aria-label="Filter by status"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              options={[
                { value: "ALL", label: "All Statuses" },
                { value: MerchantStatus.APPROVED, label: "Approved" },
                { value: MerchantStatus.PENDING, label: "Pending" },
                { value: MerchantStatus.UNDER_REVIEW, label: "Under Review" },
                { value: MerchantStatus.SUSPENDED, label: "Suspended" },
                { value: MerchantStatus.REJECTED, label: "Rejected" },
              ]}
            />
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-slate-800 bg-slate-900/40">
              {COLUMNS.map((c) => (
                <th
                  key={c.key}
                  className={cn(
                    "px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-slate-500",
                    c.align === "right" ? "text-right" : "text-left"
                  )}
                >
                  <button
                    onClick={() => toggleSort(c.key)}
                    className={cn(
                      "inline-flex items-center gap-1 hover:text-slate-300",
                      c.align === "right" && "flex-row-reverse"
                    )}
                  >
                    {c.label}
                    {sortKey === c.key ? (
                      sortDir === "asc" ? (
                        <ChevronUp className="h-3 w-3" />
                      ) : (
                        <ChevronDown className="h-3 w-3" />
                      )
                    ) : (
                      <span className="h-3 w-3" />
                    )}
                  </button>
                </th>
              ))}
              <th className="px-4 py-2.5" />
            </tr>
          </thead>
          <tbody>
            {filtered.map((m) => {
              const riskTone = RISK_TONE[m.riskTier];
              const statusTone = STATUS_TONE[m.status];
              const pendingDocs = m.documents.filter(
                (d) => d.status === DocStatus.PENDING_REVIEW
              ).length;
              return (
                <tr
                  key={m.id}
                  onClick={() => selectMerchant(m.id)}
                  className="group cursor-pointer border-b border-slate-800/60 transition-colors hover:bg-slate-800/40"
                >
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-slate-800 text-xs font-semibold text-slate-300">
                        {m.businessProfile.dba.slice(0, 2).toUpperCase()}
                      </span>
                      <div className="min-w-0">
                        <p className="truncate font-medium text-slate-100">
                          {m.legalName}
                        </p>
                        <p className="truncate text-xs text-slate-500">
                          {m.id} · {m.businessProfile.mccDescription}
                          {m.crossBorder && " · Cross-Border"}
                        </p>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-col gap-1">
                      <Badge tone={riskTone} dot>
                        {RISK_LABEL[m.riskTier]}
                      </Badge>
                      <span className="text-xs tabular-nums text-slate-500">
                        Score {m.riskScore}/100
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <span className="font-medium tabular-nums text-slate-100">
                      {formatCompactUsd(m.financialProfile.monthlyVolumeUsd)}
                    </span>
                    <p className="text-xs text-slate-500">
                      avg ${m.financialProfile.avgTicketUsd}
                    </p>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <span
                      className={cn(
                        "font-medium tabular-nums",
                        m.financialProfile.chargebackBps >= 80
                          ? "text-rose-400"
                          : m.financialProfile.chargebackBps >= 50
                          ? "text-amber-400"
                          : "text-emerald-400"
                      )}
                    >
                      {m.financialProfile.chargebackBps}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-col gap-1">
                      <Badge tone={statusTone} dot>
                        {STATUS_LABEL[m.status]}
                      </Badge>
                      {pendingDocs > 0 && (
                        <span className="inline-flex items-center gap-1 text-xs text-amber-400">
                          <FileWarning className="h-3 w-3" />
                          {pendingDocs} doc(s) pending
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        selectMerchant(m.id);
                      }}
                    >
                      Open
                    </Button>
                  </td>
                </tr>
              );
            })}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-16 text-center">
                  <p className="text-sm text-slate-400">
                    No merchants match your filters.
                  </p>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="mt-2"
                    onClick={() => {
                      setGlobalSearch("");
                      setRiskFilter("ALL");
                      setStatusFilter("ALL");
                    }}
                  >
                    Clear filters
                  </Button>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

export default function DashboardPage() {
  const { merchants } = useMerchants();
  const { selectedId, selectMerchant, view } = useSelection();

  const metrics = useMemo(() => {
    const totalVolume = merchants.reduce(
      (s, m) => s + m.financialProfile.monthlyVolumeUsd,
      0
    );
    const lifetime = merchants.reduce(
      (s, m) => s + m.financialProfile.lifetimeVolumeUsd,
      0
    );
    const highRisk = merchants.filter(
      (m) => m.riskTier === RiskTier.HIGH
    ).length;
    const pendingDocs = merchants.reduce(
      (s, m) =>
        s + m.documents.filter((d) => d.status === DocStatus.PENDING_REVIEW).length,
      0
    );
    const avgCb =
      merchants.reduce((s, m) => s + m.financialProfile.chargebackBps, 0) /
      merchants.length;
    return { totalVolume, lifetime, highRisk, pendingDocs, avgCb };
  }, [merchants]);

  const selected = selectedId
    ? merchants.find((m) => m.id === selectedId)
    : null;

  // The Helpdesk hub is a full-bleed view that owns its own scrolling layout.
  // It takes precedence over the portfolio table, but a selected merchant
  // (e.g. teleported into via a "Link to KYC Profile" macro) always wins so
  // the deep-link lands on the merchant workspace.
  if (view === "helpdesk" && !selected) {
    return (
      <div className="h-[calc(100vh-3.5rem)]">
        <HelpdeskWorkspace />
      </div>
    );
  }

  if (selected) {
    return (
      <div className="mx-auto max-w-[1400px] p-6">
        <button
          onClick={() => selectMerchant(null)}
          className="mb-4 inline-flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-200"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to portfolio
        </button>
        <MerchantDetailWorkspace merchant={selected} />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[1400px] p-6">
      <div className="mb-5">
        <h1 className="text-xl font-semibold text-slate-100">
          Operations Overview
        </h1>
        <p className="mt-0.5 text-sm text-slate-500">
          Real-time portfolio health across {merchants.length} active merchant
          accounts.
        </p>
      </div>

      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Monthly Volume"
          value={formatCompactUsd(metrics.totalVolume)}
          sub="Aggregate processing this period"
          icon={CircleDollarSign}
          tone="sky"
        />
        <MetricCard
          label="Lifetime Processed"
          value={formatCompactUsd(metrics.lifetime)}
          sub="Cumulative settled volume"
          icon={Wallet}
          tone="emerald"
        />
        <MetricCard
          label="High-Risk Accounts"
          value={String(metrics.highRisk)}
          sub={`Avg chargebacks ${metrics.avgCb.toFixed(0)} bps`}
          icon={ShieldAlert}
          tone="crimson"
        />
        <MetricCard
          label="Docs Awaiting Review"
          value={String(metrics.pendingDocs)}
          sub="Across all compliance queues"
          icon={TrendingUp}
          tone="amber"
        />
      </div>

      <MerchantTable />
    </div>
  );
}
