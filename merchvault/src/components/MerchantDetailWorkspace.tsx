"use client";

/**
 * MerchVault — Merchant Detail Workspace
 * ----------------------------------------
 * The primary tabbed operational interface for a single merchant. All six tabs
 * read from and write to MerchantContext, so any mutation (approving a doc,
 * overriding a tier, editing metadata) is reflected instantly everywhere —
 * sidebar status dots, dashboard table, notifications, and the audit timeline.
 *
 * Tabs:
 *   1. Overview   — risk gauges, processing caps, onboarding action toggles
 *   2. Profile    — structural business data with inline-editable fields
 *   3. KYC        — UBO compliance, risk-point matrix, manual overrides
 *   4. Documents  — modal previewer with live approve / reject-with-comment
 *   5. Custom     — editable key/value metadata playground + add-tag
 *   6. Audit Log  — chronological vertical timeline of analytical footprints
 */

import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  BadgeCheck,
  Ban,
  Building2,
  Check,
  Clock,
  Database,
  FileText,
  Fingerprint,
  Gauge,
  Headset,
  History,
  Inbox,
  Pencil,
  Plus,
  ShieldQuestion,
  Trash2,
  UserCheck,
  X,
} from "lucide-react";
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  FieldRow,
  Input,
  Meter,
  Modal,
  Select,
  TONE_TEXT,
  Textarea,
  Toggle,
} from "@/components/ui";
import {
  Composer,
  SmartRiskActions,
  ThreadBubble,
} from "@/components/HelpdeskWorkspace";
import { useMerchants } from "@/context/MerchantContext";
import { useSelection } from "@/context/SelectionContext";
import {
  ComplianceDocument,
  CustomField,
  DOC_TONE,
  DocStatus,
  KYC_STATUS_LABEL,
  Merchant,
  MerchantStatus,
  RISK_LABEL,
  RISK_TONE,
  RiskTier,
  STATUS_LABEL,
  STATUS_TONE,
  SanctionsFlag,
  SupportTicket,
  TICKET_CATEGORY_LABEL,
  TICKET_PRIORITY_LABEL,
  TICKET_PRIORITY_TONE,
  TICKET_STATUS_LABEL,
  TICKET_STATUS_TONE,
  TicketStatus,
  ToneKey,
  UBO,
  VerificationStatus,
} from "@/types/merchant";
import {
  cn,
  formatCompactUsd,
  formatDate,
  formatDateTime,
  formatUsd,
  relativeTime,
} from "@/lib/utils";

/* ------------------------------------------------------------------ */
/* Tab scaffold                                                        */
/* ------------------------------------------------------------------ */

type TabId =
  | "overview"
  | "profile"
  | "kyc"
  | "documents"
  | "custom"
  | "audit"
  | "support";

const TABS: { id: TabId; label: string; icon: React.ElementType }[] = [
  { id: "overview", label: "Overview", icon: Gauge },
  { id: "profile", label: "Profile", icon: Building2 },
  { id: "kyc", label: "KYC & Compliance", icon: Fingerprint },
  { id: "documents", label: "Documents", icon: FileText },
  { id: "custom", label: "Custom Data", icon: Database },
  { id: "audit", label: "Audit Log", icon: History },
  { id: "support", label: "Support & Tickets", icon: Headset },
];

const REASON_CODES = [
  "MANUAL_RISK_REVIEW",
  "REGULATORY_REQUIREMENT",
  "CHARGEBACK_BREACH",
  "KYC_REMEDIATION",
  "COMMERCIAL_DECISION",
  "FRAUD_SIGNAL",
];

/* ------------------------------------------------------------------ */
/* Root                                                                */
/* ------------------------------------------------------------------ */

export function MerchantDetailWorkspace({ merchant }: { merchant: Merchant }) {
  const [tab, setTab] = useState<TabId>("overview");
  const { requestedTab, setRequestedTab } = useSelection();
  const riskTone = RISK_TONE[merchant.riskTier];
  const statusTone = STATUS_TONE[merchant.status];

  // Macros like "Link to KYC Profile" teleport here with a requested tab
  // (e.g. "documents" or "support"). Honor it once, then clear the request.
  useEffect(() => {
    if (requestedTab) {
      setTab(requestedTab as TabId);
      setRequestedTab(null);
    }
  }, [requestedTab, setRequestedTab]);

  return (
    <div className="animate-fade-in">
      {/* Header */}
      <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-center gap-4">
          <span className="flex h-14 w-14 items-center justify-center rounded-xl bg-slate-800 text-lg font-semibold text-slate-200">
            {merchant.businessProfile.dba.slice(0, 2).toUpperCase()}
          </span>
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-xl font-semibold text-slate-100">
                {merchant.legalName}
              </h1>
              <span className="rounded bg-slate-800 px-1.5 py-0.5 font-mono text-xs text-slate-400">
                {merchant.id}
              </span>
            </div>
            <p className="mt-0.5 text-sm text-slate-500">
              {merchant.businessProfile.legalEntityType} ·{" "}
              {merchant.businessProfile.mccDescription} · Managed by{" "}
              {merchant.accountManager}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge tone={riskTone} dot>
            {RISK_LABEL[merchant.riskTier]}
          </Badge>
          <Badge tone={statusTone} dot>
            {STATUS_LABEL[merchant.status]}
          </Badge>
        </div>
      </div>

      {/* Tab strip */}
      <div className="mb-5 flex flex-wrap gap-1 border-b border-slate-800">
        {TABS.map((t) => {
          const active = tab === t.id;
          return (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={cn(
                "relative inline-flex items-center gap-2 px-3.5 py-2.5 text-sm font-medium transition-colors",
                active
                  ? "text-slate-100"
                  : "text-slate-500 hover:text-slate-300"
              )}
            >
              <t.icon className="h-4 w-4" />
              {t.label}
              {active && (
                <span className="absolute inset-x-0 -bottom-px h-0.5 rounded-full bg-sky-400" />
              )}
            </button>
          );
        })}
      </div>

      {/* Tab body */}
      {tab === "overview" && <OverviewTab merchant={merchant} />}
      {tab === "profile" && <ProfileTab merchant={merchant} />}
      {tab === "kyc" && <KycTab merchant={merchant} />}
      {tab === "documents" && <DocumentsTab merchant={merchant} />}
      {tab === "custom" && <CustomDataTab merchant={merchant} />}
      {tab === "audit" && <AuditTab merchant={merchant} />}
      {tab === "support" && <SupportTab merchant={merchant} />}
    </div>
  );
}

/* ================================================================== */
/* 1 · Overview                                                        */
/* ================================================================== */

function Gauge100({
  label,
  value,
  tone,
  caption,
}: {
  label: string;
  value: number;
  tone: ToneKey;
  caption: string;
}) {
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <span className="text-xs font-medium uppercase tracking-wide text-slate-500">
          {label}
        </span>
        <span className={cn("text-lg font-semibold tabular-nums", TONE_TEXT[tone])}>
          {value}
          <span className="text-xs text-slate-500">/100</span>
        </span>
      </div>
      <Meter value={value} tone={tone} className="mt-2" />
      <p className="mt-1.5 text-xs text-slate-500">{caption}</p>
    </div>
  );
}

function OverviewTab({ merchant }: { merchant: Merchant }) {
  const { setRollingReserve, updateCustomField } = useMerchants();
  const fin = merchant.financialProfile;
  const riskTone = RISK_TONE[merchant.riskTier];

  const cbTone: ToneKey =
    fin.chargebackBps >= 80 ? "crimson" : fin.chargebackBps >= 50 ? "amber" : "emerald";

  const flagBool = (key: string) =>
    merchant.customFields.find((f) => f.key === key)?.value === true;

  return (
    <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
      {/* Risk gauges */}
      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle>Risk Metrics</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-6 sm:grid-cols-3">
          <Gauge100
            label="Composite Risk"
            value={merchant.riskScore}
            tone={riskTone}
            caption={RISK_LABEL[merchant.riskTier]}
          />
          <Gauge100
            label="Chargeback Load"
            value={Math.min(100, fin.chargebackBps)}
            tone={cbTone}
            caption={`${fin.chargebackBps} bps current`}
          />
          <Gauge100
            label="Reserve Coverage"
            value={fin.rollingReservePct * 10}
            tone={fin.rollingReservePct >= 8 ? "crimson" : fin.rollingReservePct >= 4 ? "amber" : "emerald"}
            caption={`${fin.rollingReservePct}% rolling reserve`}
          />
        </CardContent>
      </Card>

      {/* Processing caps */}
      <Card>
        <CardHeader>
          <CardTitle>Processing Caps</CardTitle>
        </CardHeader>
        <CardContent>
          <FieldRow label="Monthly Volume">
            <span className="tabular-nums">
              {formatCompactUsd(fin.monthlyVolumeUsd)}
            </span>
          </FieldRow>
          <FieldRow label="Avg Ticket">
            <span className="tabular-nums">{formatUsd(fin.avgTicketUsd)}</span>
          </FieldRow>
          <FieldRow label="Lifetime Volume">
            <span className="tabular-nums">
              {formatCompactUsd(fin.lifetimeVolumeUsd)}
            </span>
          </FieldRow>
          <FieldRow label="KYC Status">
            {KYC_STATUS_LABEL[merchant.kycStatus]} · {merchant.kycLevel.replace("_", " ")}
          </FieldRow>
          <FieldRow label="AML Result">
            <Badge
              tone={
                merchant.amlResult === "PASSED"
                  ? "emerald"
                  : merchant.amlResult === "FAILED"
                  ? "crimson"
                  : "amber"
              }
            >
              {merchant.amlResult}
            </Badge>
          </FieldRow>
        </CardContent>
      </Card>

      {/* Rolling reserve control */}
      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle>Rolling Reserve Control</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4">
            <input
              type="range"
              min={0}
              max={10}
              step={1}
              value={fin.rollingReservePct}
              onChange={(e) =>
                setRollingReserve(merchant.id, Number(e.target.value))
              }
              className="h-1.5 flex-1 cursor-pointer appearance-none rounded-full bg-slate-700 accent-sky-500"
              aria-label="Rolling reserve percentage"
            />
            <span className="w-16 text-right text-lg font-semibold tabular-nums text-slate-100">
              {fin.rollingReservePct}%
            </span>
          </div>
          <p className="mt-2 text-xs text-slate-500">
            Adjusting the reserve writes a timestamped entry to the audit log.
            Capped at the program maximum of 10%.
          </p>
        </CardContent>
      </Card>

      {/* Onboarding action toggles */}
      <Card>
        <CardHeader>
          <CardTitle>Rapid Onboarding Toggles</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {[
            { key: "instant_payout_enabled", label: "Instant Payouts" },
            { key: "manual_review_required", label: "Manual Review" },
            { key: "high_risk_geos_blocked", label: "Block High-Risk Geos" },
            { key: "cross_border_enabled", label: "Cross-Border Settlement" },
          ].map((toggle) => {
            const exists = merchant.customFields.some(
              (f) => f.key === toggle.key
            );
            return (
              <div
                key={toggle.key}
                className={cn(
                  "flex items-center justify-between",
                  !exists && "opacity-40"
                )}
              >
                <span className="text-sm text-slate-300">{toggle.label}</span>
                <Toggle
                  checked={flagBool(toggle.key)}
                  disabled={!exists}
                  onChange={(v) =>
                    updateCustomField(merchant.id, toggle.key, v)
                  }
                  label={toggle.label}
                />
              </div>
            );
          })}
        </CardContent>
      </Card>
    </div>
  );
}

/* ================================================================== */
/* 2 · Profile (inline editable)                                       */
/* ================================================================== */

function EditableField({
  label,
  value,
  fieldKey,
  merchantId,
}: {
  label: string;
  value: string;
  fieldKey: string;
  merchantId: string;
}) {
  // Inline edit demo: edits a mirrored custom field if present, else local echo.
  const { merchants, addCustomField, updateCustomField } = useMerchants();
  const m = merchants.find((x) => x.id === merchantId)!;
  const mirrorKey = `profile_${fieldKey}`;
  const override = m.customFields.find((f) => f.key === mirrorKey);
  const display = override ? String(override.value) : value;

  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(display);

  const commit = () => {
    if (override) {
      updateCustomField(merchantId, mirrorKey, draft);
    } else {
      addCustomField(merchantId, {
        key: mirrorKey,
        value: draft,
        type: "string",
      });
    }
    setEditing(false);
  };

  return (
    <div className="flex items-center justify-between gap-4 border-b border-slate-800/60 py-2.5 last:border-0">
      <span className="text-xs font-medium uppercase tracking-wide text-slate-500">
        {label}
      </span>
      {editing ? (
        <span className="flex items-center gap-1.5">
          <Input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            className="h-7 w-48 text-right"
            autoFocus
          />
          <Button size="icon" variant="emerald" onClick={commit}>
            <Check className="h-3.5 w-3.5" />
          </Button>
          <Button
            size="icon"
            variant="ghost"
            onClick={() => {
              setDraft(display);
              setEditing(false);
            }}
          >
            <X className="h-3.5 w-3.5" />
          </Button>
        </span>
      ) : (
        <span className="group flex items-center gap-2">
          <span className="text-right text-sm text-slate-200">{display}</span>
          <button
            onClick={() => {
              setDraft(display);
              setEditing(true);
            }}
            className="text-slate-600 opacity-0 transition-opacity hover:text-sky-400 group-hover:opacity-100"
            aria-label={`Edit ${label}`}
          >
            <Pencil className="h-3.5 w-3.5" />
          </button>
        </span>
      )}
    </div>
  );
}

function ProfileTab({ merchant }: { merchant: Merchant }) {
  const bp = merchant.businessProfile;
  const fin = merchant.financialProfile;
  return (
    <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Business Identity</CardTitle>
        </CardHeader>
        <CardContent>
          <EditableField label="Legal Name" value={merchant.legalName} fieldKey="legal_name" merchantId={merchant.id} />
          <EditableField label="DBA" value={bp.dba} fieldKey="dba" merchantId={merchant.id} />
          <FieldRow label="Entity Type">{bp.legalEntityType}</FieldRow>
          <FieldRow label="EIN / Tax ID">
            <span className="font-mono">{bp.ein}</span>
          </FieldRow>
          <FieldRow label="MCC Code">
            {bp.mccCode} · {bp.mccDescription}
          </FieldRow>
          <FieldRow label="Descriptor">
            <span className="font-mono">{bp.processingDescriptor}</span>
          </FieldRow>
          <FieldRow label="Incorporated">
            {bp.incorporationState} · {formatDate(bp.incorporationDate)}
          </FieldRow>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Contact & Support</CardTitle>
        </CardHeader>
        <CardContent>
          <EditableField label="Website" value={bp.website} fieldKey="website" merchantId={merchant.id} />
          <EditableField label="Support Email" value={bp.supportEmail} fieldKey="support_email" merchantId={merchant.id} />
          <EditableField label="Support Phone" value={bp.supportPhone} fieldKey="support_phone" merchantId={merchant.id} />
          <FieldRow label="Onboarded">{formatDate(merchant.onboardedAt)}</FieldRow>
          <FieldRow label="Account Manager">{merchant.accountManager}</FieldRow>
        </CardContent>
      </Card>

      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle>Settlement Rails</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {fin.settlementRails.map((rail) => (
            <div
              key={rail.id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-800 bg-slate-950/40 px-4 py-3"
            >
              <div className="flex items-center gap-3">
                <span className="flex h-8 w-8 items-center justify-center rounded-md bg-slate-800 text-slate-400">
                  <Building2 className="h-4 w-4" />
                </span>
                <div>
                  <p className="text-sm font-medium text-slate-200">
                    {rail.bankName}
                  </p>
                  <p className="font-mono text-xs text-slate-500">
                    Acct {rail.accountMask} · Routing {rail.routingMask}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Badge tone="slate">{rail.currency}</Badge>
                {rail.primary && <Badge tone="emerald">Primary</Badge>}
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

/* ================================================================== */
/* 3 · KYC & Compliance                                                */
/* ================================================================== */

const VERIFICATION_TONE: Record<VerificationStatus, ToneKey> = {
  [VerificationStatus.VERIFIED]: "emerald",
  [VerificationStatus.PENDING]: "amber",
  [VerificationStatus.TIMEOUT]: "amber",
  [VerificationStatus.FAILED]: "crimson",
};

const SANCTIONS_TONE: Record<SanctionsFlag, ToneKey> = {
  [SanctionsFlag.CLEAR]: "emerald",
  [SanctionsFlag.PENDING]: "amber",
  [SanctionsFlag.POTENTIAL_MATCH]: "amber",
  [SanctionsFlag.CONFIRMED_HIT]: "crimson",
};

function UboCard({ ubo }: { ubo: UBO }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-800 text-sm font-semibold text-slate-300">
            {ubo.fullName
              .split(" ")
              .map((n) => n[0])
              .join("")
              .slice(0, 2)}
          </span>
          <div>
            <p className="flex items-center gap-2 text-sm font-medium text-slate-100">
              {ubo.fullName}
              {ubo.pep && <Badge tone="amber">PEP</Badge>}
            </p>
            <p className="text-xs text-slate-500">
              {ubo.role} · {ubo.ownershipPct}% · {ubo.nationality}
            </p>
          </div>
        </div>
        <span className="text-2xl font-semibold tabular-nums text-slate-300">
          {ubo.ownershipPct}%
        </span>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Badge tone={VERIFICATION_TONE[ubo.verification]} dot>
          <UserCheck className="h-3 w-3" /> {ubo.verification}
        </Badge>
        <Badge tone={SANCTIONS_TONE[ubo.sanctions]} dot>
          <ShieldQuestion className="h-3 w-3" /> {ubo.sanctions.replace("_", " ")}
        </Badge>
      </div>
      {ubo.notes && (
        <p className="mt-2 rounded-md bg-slate-900/60 px-3 py-2 text-xs text-slate-400">
          {ubo.notes}
        </p>
      )}
    </div>
  );
}

function KycTab({ merchant }: { merchant: Merchant }) {
  const { overrideRiskTier, overrideStatus } = useMerchants();
  const [overrideOpen, setOverrideOpen] = useState(false);
  const [tier, setTier] = useState<RiskTier>(merchant.riskTier);
  const [status, setStatus] = useState<MerchantStatus>(merchant.status);
  const [reason, setReason] = useState(REASON_CODES[0]);
  const [mode, setMode] = useState<"tier" | "status">("tier");

  // Risk point matrix derived from merchant signals
  const matrix = useMemo(() => {
    const fin = merchant.financialProfile;
    return [
      {
        factor: "Chargeback Rate",
        detail: `${fin.chargebackBps} bps`,
        points:
          fin.chargebackBps >= 80 ? 35 : fin.chargebackBps >= 50 ? 20 : 8,
        tone: (fin.chargebackBps >= 80
          ? "crimson"
          : fin.chargebackBps >= 50
          ? "amber"
          : "emerald") as ToneKey,
      },
      {
        factor: "MCC Risk",
        detail: merchant.businessProfile.mccDescription,
        points: merchant.customFields.some((f) => f.key === "high_risk_mcc")
          ? 18
          : 6,
        tone: merchant.customFields.some((f) => f.key === "high_risk_mcc")
          ? ("amber" as ToneKey)
          : ("emerald" as ToneKey),
      },
      {
        factor: "Cross-Border Exposure",
        detail: merchant.crossBorder ? "Enabled" : "Domestic only",
        points: merchant.crossBorder ? 14 : 4,
        tone: merchant.crossBorder ? ("amber" as ToneKey) : ("emerald" as ToneKey),
      },
      {
        factor: "PEP / Sanctions",
        detail: merchant.ubos.some((u) => u.pep)
          ? "PEP owner present"
          : "No PEP exposure",
        points: merchant.ubos.some((u) => u.pep) ? 14 : 2,
        tone: merchant.ubos.some((u) => u.pep)
          ? ("amber" as ToneKey)
          : ("emerald" as ToneKey),
      },
    ];
  }, [merchant]);

  const openOverride = (m: "tier" | "status") => {
    setMode(m);
    setTier(merchant.riskTier);
    setStatus(merchant.status);
    setReason(REASON_CODES[0]);
    setOverrideOpen(true);
  };

  const commitOverride = () => {
    if (mode === "tier") overrideRiskTier(merchant.id, tier, reason);
    else overrideStatus(merchant.id, status, reason);
    setOverrideOpen(false);
  };

  return (
    <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
      {/* UBO registry */}
      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle>Ultimate Beneficial Owners</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {merchant.ubos.map((u) => (
            <UboCard key={u.id} ubo={u} />
          ))}
        </CardContent>
      </Card>

      {/* Manual override panel */}
      <Card>
        <CardHeader>
          <CardTitle>Manual Overrides</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-3">
            <p className="text-xs uppercase tracking-wide text-slate-500">
              Current Risk Tier
            </p>
            <div className="mt-1 flex items-center justify-between">
              <Badge tone={RISK_TONE[merchant.riskTier]} dot>
                {RISK_LABEL[merchant.riskTier]}
              </Badge>
              <Button size="sm" variant="outline" onClick={() => openOverride("tier")}>
                Override
              </Button>
            </div>
          </div>
          <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-3">
            <p className="text-xs uppercase tracking-wide text-slate-500">
              Current Status
            </p>
            <div className="mt-1 flex items-center justify-between">
              <Badge tone={STATUS_TONE[merchant.status]} dot>
                {STATUS_LABEL[merchant.status]}
              </Badge>
              <Button size="sm" variant="outline" onClick={() => openOverride("status")}>
                Override
              </Button>
            </div>
          </div>
          <p className="flex items-start gap-1.5 text-xs text-slate-500">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-500" />
            All overrides require a reason code and are written to the immutable
            audit log.
          </p>
        </CardContent>
      </Card>

      {/* Risk point matrix */}
      <Card className="lg:col-span-3">
        <CardHeader>
          <CardTitle>Risk Point Matrix</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-800 text-xs uppercase tracking-wide text-slate-500">
                  <th className="py-2 text-left font-semibold">Risk Factor</th>
                  <th className="py-2 text-left font-semibold">Observation</th>
                  <th className="py-2 text-right font-semibold">Points</th>
                  <th className="py-2 text-right font-semibold">Contribution</th>
                </tr>
              </thead>
              <tbody>
                {matrix.map((row) => (
                  <tr key={row.factor} className="border-b border-slate-800/60">
                    <td className="py-2.5 font-medium text-slate-200">
                      {row.factor}
                    </td>
                    <td className="py-2.5 text-slate-400">{row.detail}</td>
                    <td className="py-2.5 text-right">
                      <span className={cn("font-semibold tabular-nums", TONE_TEXT[row.tone])}>
                        +{row.points}
                      </span>
                    </td>
                    <td className="py-2.5 text-right" style={{ width: 160 }}>
                      <Meter value={row.points} max={40} tone={row.tone} />
                    </td>
                  </tr>
                ))}
                <tr>
                  <td className="pt-3 font-semibold text-slate-100" colSpan={2}>
                    Composite Risk Score
                  </td>
                  <td className="pt-3 text-right font-semibold tabular-nums text-slate-100">
                    {merchant.riskScore}
                  </td>
                  <td className="pt-3 text-right">
                    <Badge tone={RISK_TONE[merchant.riskTier]}>
                      {RISK_LABEL[merchant.riskTier]}
                    </Badge>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Override modal */}
      <Modal
        open={overrideOpen}
        onClose={() => setOverrideOpen(false)}
        title={mode === "tier" ? "Override Risk Tier" : "Override Status"}
        description="A reason code is mandatory and will be recorded in the audit log."
        footer={
          <>
            <Button variant="ghost" onClick={() => setOverrideOpen(false)}>
              Cancel
            </Button>
            <Button variant="amber" onClick={commitOverride}>
              Apply Override
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          {mode === "tier" ? (
            <div>
              <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-slate-500">
                New Risk Tier
              </label>
              <Select
                value={tier}
                onChange={(e) => setTier(e.target.value as RiskTier)}
                options={[
                  { value: RiskTier.LOW, label: "Low Risk" },
                  { value: RiskTier.MEDIUM, label: "Medium Risk" },
                  { value: RiskTier.MEDIUM_HIGH, label: "Medium-High Risk" },
                  { value: RiskTier.HIGH, label: "High Risk" },
                ]}
              />
            </div>
          ) : (
            <div>
              <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-slate-500">
                New Status
              </label>
              <Select
                value={status}
                onChange={(e) => setStatus(e.target.value as MerchantStatus)}
                options={[
                  { value: MerchantStatus.APPROVED, label: "Approved" },
                  { value: MerchantStatus.PENDING, label: "Pending" },
                  { value: MerchantStatus.UNDER_REVIEW, label: "Under Review" },
                  { value: MerchantStatus.SUSPENDED, label: "Suspended" },
                  { value: MerchantStatus.REJECTED, label: "Rejected" },
                ]}
              />
            </div>
          )}
          <div>
            <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-slate-500">
              Reason Code (required)
            </label>
            <Select
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              options={REASON_CODES.map((r) => ({ value: r, label: r }))}
            />
          </div>
        </div>
      </Modal>
    </div>
  );
}

/* ================================================================== */
/* 4 · Documents                                                       */
/* ================================================================== */

const DOC_STATUS_LABEL: Record<DocStatus, string> = {
  [DocStatus.APPROVED]: "Approved",
  [DocStatus.PENDING_REVIEW]: "Pending Review",
  [DocStatus.REJECTED]: "Rejected",
  [DocStatus.EXPIRED]: "Expired",
};

function DocumentsTab({ merchant }: { merchant: Merchant }) {
  const { setDocumentStatus } = useMerchants();
  const [active, setActive] = useState<ComplianceDocument | null>(null);
  const [rejecting, setRejecting] = useState(false);
  const [comment, setComment] = useState("");

  const openDoc = (doc: ComplianceDocument) => {
    setActive(doc);
    setRejecting(false);
    setComment("");
  };

  const approve = () => {
    if (!active) return;
    setDocumentStatus(merchant.id, active.id, DocStatus.APPROVED);
    setActive(null);
  };

  const reject = () => {
    if (!active) return;
    setDocumentStatus(
      merchant.id,
      active.id,
      DocStatus.REJECTED,
      comment || "Rejected by reviewer."
    );
    setActive(null);
  };

  // keep modal doc in sync with latest context state
  const liveActive = active
    ? merchant.documents.find((d) => d.id === active.id) ?? active
    : null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Compliance Documents</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {merchant.documents.map((doc) => {
          const tone = DOC_TONE[doc.status];
          return (
            <div
              key={doc.id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-800 bg-slate-950/40 px-4 py-3"
            >
              <div className="flex items-center gap-3">
                <span className="flex h-9 w-9 items-center justify-center rounded-md bg-slate-800 text-slate-400">
                  <FileText className="h-4 w-4" />
                </span>
                <div>
                  <p className="text-sm font-medium text-slate-200">
                    {doc.name}
                  </p>
                  <p className="text-xs text-slate-500">
                    {doc.fileType} · {doc.sizeKb} KB · {doc.category.replace(/_/g, " ")}
                    {doc.reviewedBy && ` · reviewed by ${doc.reviewedBy}`}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Badge tone={tone} dot>
                  {DOC_STATUS_LABEL[doc.status]}
                </Badge>
                <Button size="sm" variant="outline" onClick={() => openDoc(doc)}>
                  Preview
                </Button>
              </div>
            </div>
          );
        })}
      </CardContent>

      {/* Document preview modal */}
      <Modal
        open={!!liveActive}
        onClose={() => setActive(null)}
        size="lg"
        title={liveActive?.name ?? "Document"}
        description={
          liveActive
            ? `${liveActive.fileType} · ${liveActive.sizeKb} KB · ${liveActive.category.replace(/_/g, " ")}`
            : undefined
        }
        footer={
          liveActive ? (
            rejecting ? (
              <>
                <Button variant="ghost" onClick={() => setRejecting(false)}>
                  Back
                </Button>
                <Button variant="crimson" onClick={reject}>
                  <Ban className="h-3.5 w-3.5" /> Confirm Rejection
                </Button>
              </>
            ) : (
              <>
                <Button variant="crimson" onClick={() => setRejecting(true)}>
                  <X className="h-3.5 w-3.5" /> Reject
                </Button>
                <Button variant="emerald" onClick={approve}>
                  <Check className="h-3.5 w-3.5" /> Approve
                </Button>
              </>
            )
          ) : null
        }
      >
        {liveActive && (
          <div className="space-y-4">
            {/* Mock document preview pane */}
            <div className="flex h-56 flex-col items-center justify-center rounded-lg border border-dashed border-slate-700 bg-slate-950/60">
              <FileText className="h-10 w-10 text-slate-600" />
              <p className="mt-2 text-sm text-slate-400">
                Secure preview · {liveActive.fileType}
              </p>
              <p className="text-xs text-slate-600">
                {liveActive.name}
              </p>
            </div>

            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="rounded-md bg-slate-950/40 px-3 py-2">
                <p className="text-xs text-slate-500">Status</p>
                <Badge tone={DOC_TONE[liveActive.status]}>
                  {DOC_STATUS_LABEL[liveActive.status]}
                </Badge>
              </div>
              <div className="rounded-md bg-slate-950/40 px-3 py-2">
                <p className="text-xs text-slate-500">Uploaded</p>
                <p className="text-slate-300">
                  {formatDateTime(liveActive.uploadedAt)}
                </p>
              </div>
            </div>

            {liveActive.comment && (
              <div className="rounded-md border border-slate-800 bg-slate-950/40 px-3 py-2 text-sm text-slate-400">
                <span className="text-xs uppercase tracking-wide text-slate-500">
                  Reviewer note
                </span>
                <p className="mt-0.5">{liveActive.comment}</p>
              </div>
            )}

            {rejecting && (
              <div>
                <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-slate-500">
                  Rejection comment
                </label>
                <Textarea
                  rows={3}
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  placeholder="Explain why this document is being rejected…"
                  autoFocus
                />
              </div>
            )}
          </div>
        )}
      </Modal>
    </Card>
  );
}

/* ================================================================== */
/* 5 · Custom Data                                                     */
/* ================================================================== */

function CustomDataTab({ merchant }: { merchant: Merchant }) {
  const { updateCustomField, addCustomField, removeCustomField } =
    useMerchants();
  const [addOpen, setAddOpen] = useState(false);
  const [newKey, setNewKey] = useState("");
  const [newValue, setNewValue] = useState("");
  const [newType, setNewType] = useState<"string" | "number" | "boolean">(
    "string"
  );

  const commitNew = () => {
    if (!newKey.trim()) return;
    let value: string | number | boolean = newValue;
    if (newType === "number") value = Number(newValue) || 0;
    if (newType === "boolean") value = newValue === "true";
    addCustomField(merchant.id, {
      key: newKey.trim(),
      value,
      type: newType,
    });
    setNewKey("");
    setNewValue("");
    setNewType("string");
    setAddOpen(false);
  };

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle>Custom Metadata Registry</CardTitle>
        <Button size="sm" variant="secondary" onClick={() => setAddOpen(true)}>
          <Plus className="h-3.5 w-3.5" /> Add New Tag
        </Button>
      </CardHeader>
      <CardContent>
        <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-4 font-mono text-sm">
          <p className="text-slate-500">{"{"}</p>
          <div className="space-y-1.5 py-1 pl-4">
            {merchant.customFields.map((field) => (
              <CustomFieldRow
                key={field.key}
                field={field}
                onChange={(v) => updateCustomField(merchant.id, field.key, v)}
                onRemove={() => removeCustomField(merchant.id, field.key)}
              />
            ))}
          </div>
          <p className="text-slate-500">{"}"}</p>
        </div>
      </CardContent>

      <Modal
        open={addOpen}
        onClose={() => setAddOpen(false)}
        title="Add Custom Metadata Tag"
        description="Tags are immediately written to the merchant record and audit log."
        footer={
          <>
            <Button variant="ghost" onClick={() => setAddOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={commitNew}>
              Add Tag
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <div>
            <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-slate-500">
              Key
            </label>
            <Input
              value={newKey}
              onChange={(e) => setNewKey(e.target.value)}
              placeholder="e.g. payout_hold_days"
            />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-1">
              <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-slate-500">
                Type
              </label>
              <Select
                value={newType}
                onChange={(e) =>
                  setNewType(e.target.value as "string" | "number" | "boolean")
                }
                options={[
                  { value: "string", label: "String" },
                  { value: "number", label: "Number" },
                  { value: "boolean", label: "Boolean" },
                ]}
              />
            </div>
            <div className="col-span-2">
              <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-slate-500">
                Value
              </label>
              {newType === "boolean" ? (
                <Select
                  value={newValue || "true"}
                  onChange={(e) => setNewValue(e.target.value)}
                  options={[
                    { value: "true", label: "true" },
                    { value: "false", label: "false" },
                  ]}
                />
              ) : (
                <Input
                  value={newValue}
                  onChange={(e) => setNewValue(e.target.value)}
                  type={newType === "number" ? "number" : "text"}
                  placeholder={newType === "number" ? "0" : "value"}
                />
              )}
            </div>
          </div>
        </div>
      </Modal>
    </Card>
  );
}

function CustomFieldRow({
  field,
  onChange,
  onRemove,
}: {
  field: CustomField;
  onChange: (v: string | number | boolean) => void;
  onRemove: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(String(field.value));

  const commit = () => {
    let v: string | number | boolean = draft;
    if (field.type === "number") v = Number(draft) || 0;
    if (field.type === "boolean") v = draft === "true";
    onChange(v);
    setEditing(false);
  };

  const valueColor =
    field.type === "boolean"
      ? field.value
        ? "text-emerald-400"
        : "text-rose-400"
      : field.type === "number"
      ? "text-amber-300"
      : "text-sky-300";

  return (
    <div className="group flex items-center gap-2">
      <span className="text-slate-400">&quot;{field.key}&quot;</span>
      <span className="text-slate-600">:</span>
      {editing ? (
        <span className="flex items-center gap-1.5">
          {field.type === "boolean" ? (
            <Select
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              className="h-7 w-24"
              options={[
                { value: "true", label: "true" },
                { value: "false", label: "false" },
              ]}
            />
          ) : (
            <Input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              className="h-7 w-44"
              type={field.type === "number" ? "number" : "text"}
              autoFocus
            />
          )}
          <Button size="icon" variant="emerald" onClick={commit}>
            <Check className="h-3.5 w-3.5" />
          </Button>
          <Button
            size="icon"
            variant="ghost"
            onClick={() => {
              setDraft(String(field.value));
              setEditing(false);
            }}
          >
            <X className="h-3.5 w-3.5" />
          </Button>
        </span>
      ) : (
        <>
          <span className={valueColor}>
            {field.type === "string" ? `"${field.value}"` : String(field.value)}
          </span>
          <span className="ml-auto flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
            <button
              onClick={() => {
                setDraft(String(field.value));
                setEditing(true);
              }}
              className="text-slate-600 hover:text-sky-400"
              aria-label={`Edit ${field.key}`}
            >
              <Pencil className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={onRemove}
              className="text-slate-600 hover:text-rose-400"
              aria-label={`Remove ${field.key}`}
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </span>
        </>
      )}
    </div>
  );
}

/* ================================================================== */
/* 6 · Audit Log                                                       */
/* ================================================================== */

const AUDIT_TONE: Record<string, ToneKey> = {
  RISK: "amber",
  KYC: "emerald",
  DOCUMENT: "slate",
  OVERRIDE: "crimson",
  METADATA: "slate",
  SYSTEM: "slate",
};

const AUDIT_ICON: Record<string, React.ElementType> = {
  RISK: Gauge,
  KYC: BadgeCheck,
  DOCUMENT: FileText,
  OVERRIDE: AlertTriangle,
  METADATA: Database,
  SYSTEM: Activity,
};

function AuditTab({ merchant }: { merchant: Merchant }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Audit Timeline</CardTitle>
      </CardHeader>
      <CardContent>
        <ol className="relative ml-3 border-l border-slate-800">
          {merchant.auditLog.map((event) => {
            const tone = AUDIT_TONE[event.category] ?? "slate";
            const Icon = AUDIT_ICON[event.category] ?? Clock;
            return (
              <li key={event.id} className="mb-5 ml-6 last:mb-0">
                <span
                  className={cn(
                    "absolute -left-[13px] flex h-6 w-6 items-center justify-center rounded-full ring-4 ring-slate-950",
                    tone === "emerald" && "bg-emerald-500/20 text-emerald-400",
                    tone === "amber" && "bg-amber-500/20 text-amber-400",
                    tone === "crimson" && "bg-rose-500/20 text-rose-400",
                    tone === "slate" && "bg-slate-700/40 text-slate-400"
                  )}
                >
                  <Icon className="h-3 w-3" />
                </span>
                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-sm font-medium text-slate-100">
                    {event.action}
                  </p>
                  <Badge tone={tone}>{event.category}</Badge>
                  <span className="text-xs text-slate-500">
                    {formatDateTime(event.timestamp)}
                  </span>
                </div>
                <p className="mt-0.5 text-sm text-slate-400">{event.detail}</p>
                <p className="mt-0.5 text-xs text-slate-600">
                  by {event.actor}
                </p>
              </li>
            );
          })}
        </ol>
      </CardContent>
    </Card>
  );
}

/* ================================================================== */
/* 7 · Support & Tickets                                               */
/* ================================================================== */

function SupportTicketRow({
  ticket,
  active,
  onSelect,
}: {
  ticket: SupportTicket;
  active: boolean;
  onSelect: () => void;
}) {
  const priorityTone = TICKET_PRIORITY_TONE[ticket.priority];
  const statusTone = TICKET_STATUS_TONE[ticket.status];
  const lastMessage = ticket.thread[ticket.thread.length - 1];

  return (
    <button
      onClick={onSelect}
      className={cn(
        "w-full rounded-lg border px-3.5 py-3 text-left transition-colors",
        active
          ? "border-sky-500/40 bg-sky-500/10"
          : "border-slate-800 bg-slate-900/40 hover:border-slate-700 hover:bg-slate-900/70"
      )}
    >
      <div className="flex items-center gap-2">
        <span className="font-mono text-xs text-slate-400">
          {ticket.ticketId}
        </span>
        <span
          className={cn(
            "ml-auto h-2 w-2 shrink-0 rounded-full",
            priorityTone === "crimson" && "bg-rose-400",
            priorityTone === "amber" && "bg-amber-400",
            priorityTone === "emerald" && "bg-emerald-400",
            priorityTone === "slate" && "bg-slate-500"
          )}
        />
      </div>
      <p className="mt-1 truncate text-sm font-medium text-slate-100">
        {ticket.subject}
      </p>
      <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
        <Badge tone={statusTone}>{TICKET_STATUS_LABEL[ticket.status]}</Badge>
        <Badge tone={priorityTone}>
          {TICKET_PRIORITY_LABEL[ticket.priority]}
        </Badge>
        <span className="text-[11px] text-slate-500">
          {relativeTime(ticket.updatedAt)}
        </span>
      </div>
      {lastMessage && (
        <p className="mt-1.5 truncate text-xs text-slate-500">
          {lastMessage.isInternalNote ? "[Internal] " : ""}
          {lastMessage.messageBody}
        </p>
      )}
    </button>
  );
}

function SupportTab({ merchant }: { merchant: Merchant }) {
  const { getMerchantTickets } = useMerchants();
  const tickets = getMerchantTickets(merchant.id);

  const [selectedTicketId, setSelectedTicketId] = useState<string | null>(
    tickets[0]?.ticketId ?? null
  );

  // Keep selection valid as tickets change (sorting, new replies, etc.).
  const selectedTicket =
    tickets.find((t) => t.ticketId === selectedTicketId) ?? tickets[0] ?? null;

  const openCount = tickets.filter(
    (t) => t.status !== TicketStatus.RESOLVED
  ).length;

  if (tickets.length === 0) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center gap-3 py-16 text-center">
          <span className="flex h-12 w-12 items-center justify-center rounded-full bg-slate-800 text-slate-500">
            <Inbox className="h-6 w-6" />
          </span>
          <div>
            <p className="text-sm font-medium text-slate-200">
              No support tickets
            </p>
            <p className="mt-0.5 text-sm text-slate-500">
              {merchant.legalName} has no open or historical helpdesk threads.
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[300px_minmax(0,1fr)]">
      {/* Ticket list */}
      <div>
        <div className="mb-2 flex items-center justify-between px-1">
          <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            Tickets
          </span>
          <Badge tone={openCount > 0 ? "crimson" : "emerald"}>
            {openCount} Open
          </Badge>
        </div>
        <div className="flex flex-col gap-2">
          {tickets.map((ticket) => (
            <SupportTicketRow
              key={ticket.ticketId}
              ticket={ticket}
              active={selectedTicket?.ticketId === ticket.ticketId}
              onSelect={() => setSelectedTicketId(ticket.ticketId)}
            />
          ))}
        </div>
      </div>

      {/* Conversation pane */}
      {selectedTicket ? (
        <div className="flex flex-col overflow-hidden rounded-xl border border-slate-800 bg-slate-950/40">
          {/* Header */}
          <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-800 px-4 py-3.5">
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs text-slate-400">
                  {selectedTicket.ticketId}
                </span>
                <Badge tone={TICKET_STATUS_TONE[selectedTicket.status]} dot>
                  {TICKET_STATUS_LABEL[selectedTicket.status]}
                </Badge>
                <Badge tone={TICKET_PRIORITY_TONE[selectedTicket.priority]} dot>
                  {TICKET_PRIORITY_LABEL[selectedTicket.priority]}
                </Badge>
              </div>
              <p className="mt-1 text-sm font-semibold text-slate-100">
                {selectedTicket.subject}
              </p>
              <p className="mt-0.5 text-xs text-slate-500">
                {TICKET_CATEGORY_LABEL[selectedTicket.category]} · Assigned to{" "}
                {selectedTicket.assignedTo}
              </p>
            </div>
          </div>

          {/* Thread */}
          <div className="flex flex-col gap-3 px-4 py-4">
            {selectedTicket.thread.map((message) => (
              <ThreadBubble key={message.id} message={message} />
            ))}
          </div>

          {/* Action rail */}
          <div className="px-4 pb-3">
            <SmartRiskActions ticket={selectedTicket} />
          </div>

          {/* Composer */}
          <Composer ticket={selectedTicket} />
        </div>
      ) : null}
    </div>
  );
}
