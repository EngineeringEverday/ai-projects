"use client";

/**
 * MerchVault — Helpdesk & Communications Hub
 * --------------------------------------------
 * The integrated support console. A dense, three-column operations surface:
 *
 *   • LEFT   — Filter sidebar: Category · Assignment · Priority · Status, each
 *              with live counts. A header strip surfaces live Open vs Urgent
 *              badge counts across the whole queue.
 *   • CENTER — Ticket feed: a chronological (newest-activity-first) list of
 *              tickets showing Ticket ID, Merchant Name, subject snippet,
 *              relative time ("4m ago"), and a color-coded priority pill.
 *   • RIGHT  — Conversation pane: the selected ticket's full thread rendered
 *              chronologically. Public messages render on a light-blue ground;
 *              internal staff notes render on a soft-amber ground with a lock
 *              icon and the [INTERNAL ONLY: Hidden from Merchant] microcopy.
 *
 * Interactivity (all functional, no placeholders):
 *   • Public / Internal split-toggle on the composer. The active persona
 *     (from the top-bar switcher) is attributed to every post in real time.
 *   • Smart Risk Actions widget — "Escalate to Risk Team" (assign Jordan Lee +
 *     priority → Urgent + internal note) and "Link to KYC Profile" (teleport
 *     into the merchant's Documents view). KYC-blocker tickets with a linked
 *     document can be resolved-with-approve in one action.
 *
 * Every mutation flows through MerchantContext, so status/priority pills and
 * counts re-tint via Tailwind transitions instantly — no page refresh.
 */

import { useMemo, useState } from "react";
import {
  ArrowRight,
  CheckCircle2,
  Filter,
  Headset,
  Inbox,
  Lock,
  MessageSquare,
  Send,
  ShieldAlert,
  Sparkles,
  TriangleAlert,
} from "lucide-react";
import { Badge, Button, Card, Textarea } from "@/components/ui";
import { useMerchants } from "@/context/MerchantContext";
import { useSelection } from "@/context/SelectionContext";
import {
  PERSONAS,
  SupportTicket,
  TICKET_CATEGORY_LABEL,
  TICKET_PRIORITY_LABEL,
  TICKET_PRIORITY_TONE,
  TICKET_STATUS_LABEL,
  TICKET_STATUS_TONE,
  ThreadMessage,
  TicketCategory,
  TicketPriority,
  TicketStatus,
  UNASSIGNED,
} from "@/types/merchant";
import { cn, formatDateTime, relativeTime } from "@/lib/utils";

/* ------------------------------------------------------------------ */
/* Filter model                                                        */
/* ------------------------------------------------------------------ */

type CategoryFilter = TicketCategory | "ALL";
type PriorityFilter = TicketPriority | "ALL";
type StatusFilter = TicketStatus | "ALL";
type AssignmentFilter = "ALL" | "UNASSIGNED" | string; // string = persona name

const CATEGORY_ORDER: TicketCategory[] = [
  TicketCategory.KYC_BLOCKER,
  TicketCategory.CHARGEBACK_DISPUTE,
  TicketCategory.SETTLEMENT_DELAY,
  TicketCategory.TECHNICAL_API,
  TicketCategory.BILLING_QUERY,
];

const PRIORITY_ORDER: TicketPriority[] = [
  TicketPriority.URGENT,
  TicketPriority.HIGH,
  TicketPriority.MEDIUM,
  TicketPriority.LOW,
];

const STATUS_ORDER: TicketStatus[] = [
  TicketStatus.OPEN,
  TicketStatus.IN_PROGRESS,
  TicketStatus.PENDING_MERCHANT,
  TicketStatus.RESOLVED,
];

/** Sort weight so the queue surfaces the most pressing tickets first. */
const PRIORITY_WEIGHT: Record<TicketPriority, number> = {
  [TicketPriority.URGENT]: 0,
  [TicketPriority.HIGH]: 1,
  [TicketPriority.MEDIUM]: 2,
  [TicketPriority.LOW]: 3,
};

/* ------------------------------------------------------------------ */
/* Left — filter sidebar                                               */
/* ------------------------------------------------------------------ */

function FilterGroup<T extends string>({
  label,
  options,
}: {
  label: string;
  options: {
    value: T;
    label: string;
    count: number;
    active: boolean;
    onSelect: () => void;
    dot?: string;
  }[];
}) {
  return (
    <div>
      <p className="px-2 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-600">
        {label}
      </p>
      <div className="flex flex-col gap-0.5">
        {options.map((o) => (
          <button
            key={o.value}
            onClick={o.onSelect}
            className={cn(
              "flex items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm transition-colors",
              o.active
                ? "bg-slate-800 text-slate-100"
                : "text-slate-400 hover:bg-slate-900 hover:text-slate-200"
            )}
          >
            {o.dot && (
              <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full", o.dot)} />
            )}
            <span className="flex-1 truncate">{o.label}</span>
            <span
              className={cn(
                "rounded px-1.5 py-0.5 text-[11px] tabular-nums",
                o.active
                  ? "bg-slate-700 text-slate-200"
                  : "bg-slate-800/80 text-slate-500"
              )}
            >
              {o.count}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

function FilterSidebar({
  tickets,
  category,
  setCategory,
  priority,
  setPriority,
  status,
  setStatus,
  assignment,
  setAssignment,
}: {
  tickets: SupportTicket[];
  category: CategoryFilter;
  setCategory: (c: CategoryFilter) => void;
  priority: PriorityFilter;
  setPriority: (p: PriorityFilter) => void;
  status: StatusFilter;
  setStatus: (s: StatusFilter) => void;
  assignment: AssignmentFilter;
  setAssignment: (a: AssignmentFilter) => void;
}) {
  const countBy = <K extends keyof SupportTicket>(
    field: K,
    value: SupportTicket[K]
  ) => tickets.filter((t) => t[field] === value).length;

  const assigneeCount = (name: string) =>
    tickets.filter((t) => t.assignedTo === name).length;

  return (
    <aside className="flex w-60 shrink-0 flex-col gap-5 overflow-y-auto border-r border-slate-800 bg-slate-950/40 p-4">
      <div className="flex items-center gap-2 text-sm font-medium text-slate-300">
        <Filter className="h-4 w-4 text-slate-500" />
        Filters
      </div>

      <FilterGroup<CategoryFilter>
        label="Category"
        options={[
          {
            value: "ALL",
            label: "All Categories",
            count: tickets.length,
            active: category === "ALL",
            onSelect: () => setCategory("ALL"),
          },
          ...CATEGORY_ORDER.map((c) => ({
            value: c,
            label: TICKET_CATEGORY_LABEL[c],
            count: countBy("category", c),
            active: category === c,
            onSelect: () => setCategory(c),
          })),
        ]}
      />

      <FilterGroup<AssignmentFilter>
        label="Assignment"
        options={[
          {
            value: "ALL",
            label: "Anyone",
            count: tickets.length,
            active: assignment === "ALL",
            onSelect: () => setAssignment("ALL"),
          },
          {
            value: "UNASSIGNED",
            label: UNASSIGNED,
            count: assigneeCount(UNASSIGNED),
            active: assignment === "UNASSIGNED",
            onSelect: () => setAssignment("UNASSIGNED"),
          },
          ...PERSONAS.map((p) => ({
            value: p.name,
            label: p.name,
            count: assigneeCount(p.name),
            active: assignment === p.name,
            onSelect: () => setAssignment(p.name),
          })),
        ]}
      />

      <FilterGroup<PriorityFilter>
        label="Priority"
        options={[
          {
            value: "ALL",
            label: "All Priorities",
            count: tickets.length,
            active: priority === "ALL",
            onSelect: () => setPriority("ALL"),
          },
          ...PRIORITY_ORDER.map((p) => ({
            value: p,
            label: TICKET_PRIORITY_LABEL[p],
            count: countBy("priority", p),
            active: priority === p,
            onSelect: () => setPriority(p),
            dot:
              TICKET_PRIORITY_TONE[p] === "crimson"
                ? "bg-rose-400"
                : TICKET_PRIORITY_TONE[p] === "amber"
                ? "bg-amber-400"
                : "bg-emerald-400",
          })),
        ]}
      />

      <FilterGroup<StatusFilter>
        label="Status"
        options={[
          {
            value: "ALL",
            label: "All Statuses",
            count: tickets.length,
            active: status === "ALL",
            onSelect: () => setStatus("ALL"),
          },
          ...STATUS_ORDER.map((s) => ({
            value: s,
            label: TICKET_STATUS_LABEL[s],
            count: countBy("status", s),
            active: status === s,
            onSelect: () => setStatus(s),
            dot:
              TICKET_STATUS_TONE[s] === "crimson"
                ? "bg-rose-400"
                : TICKET_STATUS_TONE[s] === "amber"
                ? "bg-amber-400"
                : "bg-emerald-400",
          })),
        ]}
      />
    </aside>
  );
}

/* ------------------------------------------------------------------ */
/* Center — ticket feed                                                */
/* ------------------------------------------------------------------ */

function TicketRow({
  ticket,
  merchantName,
  active,
  onSelect,
}: {
  ticket: SupportTicket;
  merchantName: string;
  active: boolean;
  onSelect: () => void;
}) {
  const priorityTone = TICKET_PRIORITY_TONE[ticket.priority];
  const statusTone = TICKET_STATUS_TONE[ticket.status];
  const lastMsg = ticket.thread[ticket.thread.length - 1];

  return (
    <button
      onClick={onSelect}
      className={cn(
        "relative block w-full border-b border-slate-800/60 px-4 py-3 text-left transition-colors",
        active ? "bg-slate-800/60" : "hover:bg-slate-900/60"
      )}
    >
      {active && (
        <span className="absolute inset-y-0 left-0 w-0.5 bg-sky-400" />
      )}
      <div className="flex items-center gap-2">
        <span
          className={cn(
            "h-1.5 w-1.5 shrink-0 rounded-full transition-colors",
            priorityTone === "crimson" && "bg-rose-400",
            priorityTone === "amber" && "bg-amber-400",
            priorityTone === "emerald" && "bg-emerald-400"
          )}
        />
        <span className="font-mono text-xs text-slate-500">
          {ticket.ticketId}
        </span>
        <span className="truncate text-sm font-medium text-slate-100">
          {merchantName}
        </span>
        <span className="ml-auto shrink-0 text-[11px] text-slate-500">
          {relativeTime(ticket.updatedAt)}
        </span>
      </div>
      <p className="mt-1 truncate text-sm text-slate-300">{ticket.subject}</p>
      {lastMsg && (
        <p className="mt-0.5 truncate text-xs text-slate-500">
          {lastMsg.isInternalNote && (
            <Lock className="mr-1 inline h-3 w-3 align-[-1px] text-amber-400" />
          )}
          {lastMsg.fromStaff ? `${lastMsg.sender}: ` : ""}
          {lastMsg.messageBody}
        </p>
      )}
      <div className="mt-2 flex items-center gap-1.5">
        <Badge tone={priorityTone}>
          {TICKET_PRIORITY_LABEL[ticket.priority]}
        </Badge>
        <Badge tone={statusTone} dot>
          {TICKET_STATUS_LABEL[ticket.status]}
        </Badge>
        <span className="ml-auto truncate text-[11px] text-slate-600">
          {ticket.assignedTo}
        </span>
      </div>
    </button>
  );
}

/* ------------------------------------------------------------------ */
/* Right — conversation thread                                         */
/* ------------------------------------------------------------------ */

export function ThreadBubble({ message }: { message: ThreadMessage }) {
  if (message.isInternalNote) {
    // Internal staff note — soft amber ground, lock icon, hidden-from-merchant.
    return (
      <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 transition-colors">
        <div className="flex items-center gap-2">
          <Lock className="h-3.5 w-3.5 text-amber-400" />
          <span className="text-sm font-medium text-amber-200">
            {message.sender}
          </span>
          <span className="rounded bg-amber-500/20 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-300">
            Internal Note
          </span>
          <span className="ml-auto text-[11px] text-amber-400/70">
            {relativeTime(message.timestamp)}
          </span>
        </div>
        <p className="mt-1.5 text-sm text-amber-50/90">{message.messageBody}</p>
        <p className="mt-2 text-[11px] font-medium uppercase tracking-wide text-amber-400/80">
          [INTERNAL ONLY: Hidden from Merchant]
        </p>
      </div>
    );
  }

  // Public message — staff replies on light-blue ground (right-aligned feel),
  // merchant messages on neutral slate ground.
  if (message.fromStaff) {
    return (
      <div className="rounded-lg border border-sky-500/30 bg-sky-500/10 px-4 py-3 transition-colors">
        <div className="flex items-center gap-2">
          <MessageSquare className="h-3.5 w-3.5 text-sky-300" />
          <span className="text-sm font-medium text-sky-100">
            {message.sender}
          </span>
          <span className="rounded bg-sky-500/20 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-sky-200">
            Public Reply
          </span>
          <span className="ml-auto text-[11px] text-sky-300/70">
            {relativeTime(message.timestamp)}
          </span>
        </div>
        <p className="mt-1.5 text-sm text-sky-50/90">{message.messageBody}</p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/70 px-4 py-3">
      <div className="flex items-center gap-2">
        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-slate-700 text-[10px] font-semibold text-slate-200">
          {message.sender.slice(0, 1)}
        </span>
        <span className="text-sm font-medium text-slate-200">
          {message.sender}
        </span>
        <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-400">
          Merchant
        </span>
        <span className="ml-auto text-[11px] text-slate-500">
          {relativeTime(message.timestamp)}
        </span>
      </div>
      <p className="mt-1.5 text-sm text-slate-300">{message.messageBody}</p>
    </div>
  );
}

export function SmartRiskActions({ ticket }: { ticket: SupportTicket }) {
  const { escalateToRisk, resolveTicket } = useMerchants();
  const { openMerchantTab } = useSelection();

  const isResolved = ticket.status === TicketStatus.RESOLVED;
  const hasLinkedDoc = !!ticket.linkedDocumentId;

  return (
    <Card className="p-3">
      <div className="mb-2 flex items-center gap-1.5 px-1">
        <Sparkles className="h-3.5 w-3.5 text-sky-400" />
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          Smart Risk Actions
        </span>
      </div>
      <div className="flex flex-col gap-2">
        <Button
          variant="outline"
          size="sm"
          className="justify-start"
          onClick={() => escalateToRisk(ticket.ticketId)}
        >
          <ShieldAlert className="h-3.5 w-3.5 text-rose-400" />
          Escalate to Risk Team
        </Button>

        {hasLinkedDoc && (
          <Button
            variant="outline"
            size="sm"
            className="justify-start"
            onClick={() =>
              openMerchantTab(ticket.merchantId, "documents")
            }
          >
            <ArrowRight className="h-3.5 w-3.5 text-sky-400" />
            Link to KYC Profile
          </Button>
        )}

        {hasLinkedDoc && !isResolved ? (
          <Button
            variant="emerald"
            size="sm"
            className="justify-start"
            onClick={() => resolveTicket(ticket.ticketId, true)}
          >
            <CheckCircle2 className="h-3.5 w-3.5" />
            Resolve &amp; Approve KYC Doc
          </Button>
        ) : (
          !isResolved && (
            <Button
              variant="emerald"
              size="sm"
              className="justify-start"
              onClick={() => resolveTicket(ticket.ticketId)}
            >
              <CheckCircle2 className="h-3.5 w-3.5" />
              Mark Resolved
            </Button>
          )
        )}
      </div>
      {hasLinkedDoc && (
        <p className="mt-2 flex items-start gap-1.5 px-1 text-[11px] text-slate-500">
          <TriangleAlert className="mt-0.5 h-3 w-3 shrink-0 text-amber-500" />
          Linked to blocked KYC document {ticket.linkedDocumentId}. Resolving
          can approve it in one action.
        </p>
      )}
    </Card>
  );
}

export function Composer({ ticket }: { ticket: SupportTicket }) {
  const { postTicketReply, activePersona } = useMerchants();
  const [body, setBody] = useState("");
  const [internal, setInternal] = useState(false);

  const persona = PERSONAS.find((p) => p.id === activePersona)!;

  const submit = () => {
    if (!body.trim()) return;
    postTicketReply(ticket.ticketId, body, internal);
    setBody("");
  };

  return (
    <div
      className={cn(
        "border-t border-slate-800 p-4 transition-colors",
        internal ? "bg-amber-500/5" : "bg-sky-500/5"
      )}
    >
      {/* Public / Internal split-toggle */}
      <div className="mb-2.5 inline-flex rounded-lg border border-slate-800 bg-slate-950/60 p-0.5">
        <button
          onClick={() => setInternal(false)}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
            !internal
              ? "bg-sky-500/20 text-sky-200 ring-1 ring-inset ring-sky-500/40"
              : "text-slate-400 hover:text-slate-200"
          )}
        >
          <MessageSquare className="h-3.5 w-3.5" />
          Public Message
        </button>
        <button
          onClick={() => setInternal(true)}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
            internal
              ? "bg-amber-500/20 text-amber-200 ring-1 ring-inset ring-amber-500/40"
              : "text-slate-400 hover:text-slate-200"
          )}
        >
          <Lock className="h-3.5 w-3.5" />
          Internal Staff Note
        </button>
      </div>

      <Textarea
        rows={3}
        value={body}
        onChange={(e) => setBody(e.target.value)}
        placeholder={
          internal
            ? "Add an internal note — hidden from the merchant…"
            : `Reply to the merchant as ${persona.name}…`
        }
        className={cn(
          internal &&
            "border-amber-500/40 bg-amber-500/5 focus-visible:ring-amber-500/40 focus-visible:border-amber-600"
        )}
      />

      <div className="mt-2.5 flex items-center justify-between">
        {/* Persona attribution — posts are attributed to the active persona */}
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-sky-500/20 text-[10px] font-semibold text-sky-300">
            {persona.initials}
          </span>
          Posting as{" "}
          <span className="font-medium text-slate-300">{persona.name}</span>
          <span className="text-slate-600">· {persona.role}</span>
        </div>
        <Button
          variant={internal ? "amber" : "primary"}
          size="sm"
          onClick={submit}
          disabled={!body.trim()}
        >
          {internal ? (
            <Lock className="h-3.5 w-3.5" />
          ) : (
            <Send className="h-3.5 w-3.5" />
          )}
          {internal ? "Post Internal Note" : "Send Public Reply"}
        </Button>
      </div>
    </div>
  );
}

function ConversationPane({
  ticket,
  merchantName,
}: {
  ticket: SupportTicket | null;
  merchantName: string;
}) {
  if (!ticket) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center">
        <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-slate-800/60 text-slate-500">
          <Inbox className="h-6 w-6" />
        </span>
        <div>
          <p className="text-sm font-medium text-slate-300">
            Select a ticket
          </p>
          <p className="mt-0.5 text-xs text-slate-500">
            Choose a conversation from the queue to view its thread.
          </p>
        </div>
      </div>
    );
  }

  const priorityTone = TICKET_PRIORITY_TONE[ticket.priority];
  const statusTone = TICKET_STATUS_TONE[ticket.status];

  return (
    <div className="flex min-w-0 flex-1 flex-col">
      {/* Thread header */}
      <div className="border-b border-slate-800 px-5 py-3.5">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-xs text-slate-500">
            {ticket.ticketId}
          </span>
          <h2 className="text-sm font-semibold text-slate-100">
            {ticket.subject}
          </h2>
          <Badge tone={priorityTone} className="ml-auto">
            {TICKET_PRIORITY_LABEL[ticket.priority]}
          </Badge>
          <Badge tone={statusTone} dot>
            {TICKET_STATUS_LABEL[ticket.status]}
          </Badge>
        </div>
        <p className="mt-1 text-xs text-slate-500">
          {merchantName} · {TICKET_CATEGORY_LABEL[ticket.category]} · Assigned
          to{" "}
          <span className="text-slate-400">{ticket.assignedTo}</span> · Opened{" "}
          {formatDateTime(ticket.createdAt)}
        </p>
      </div>

      <div className="flex min-h-0 flex-1">
        {/* Chronological thread */}
        <div className="flex-1 space-y-3 overflow-y-auto p-5">
          {ticket.thread.map((m) => (
            <ThreadBubble key={m.id} message={m} />
          ))}
        </div>

        {/* Action rail */}
        <div className="w-64 shrink-0 space-y-3 overflow-y-auto border-l border-slate-800 bg-slate-950/40 p-3">
          <SmartRiskActions ticket={ticket} />
        </div>
      </div>

      <Composer ticket={ticket} />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Root                                                                */
/* ------------------------------------------------------------------ */

export function HelpdeskWorkspace() {
  const { tickets, merchants } = useMerchants();

  const [category, setCategory] = useState<CategoryFilter>("ALL");
  const [priority, setPriority] = useState<PriorityFilter>("ALL");
  const [status, setStatus] = useState<StatusFilter>("ALL");
  const [assignment, setAssignment] = useState<AssignmentFilter>("ALL");
  const [selectedTicketId, setSelectedTicketId] = useState<string | null>(
    () => {
      // Default selection: the most urgent open ticket, else the first.
      const sorted = [...tickets].sort(
        (a, b) => PRIORITY_WEIGHT[a.priority] - PRIORITY_WEIGHT[b.priority]
      );
      return sorted[0]?.ticketId ?? null;
    }
  );

  const merchantName = (id: string) =>
    merchants.find((m) => m.id === id)?.legalName ?? id;

  // Live header counts across the entire queue.
  const openCount = tickets.filter(
    (t) => t.status !== TicketStatus.RESOLVED
  ).length;
  const urgentCount = tickets.filter(
    (t) => t.priority === TicketPriority.URGENT
  ).length;

  const visible = useMemo(() => {
    return tickets
      .filter((t) => {
        if (category !== "ALL" && t.category !== category) return false;
        if (priority !== "ALL" && t.priority !== priority) return false;
        if (status !== "ALL" && t.status !== status) return false;
        if (assignment === "UNASSIGNED" && t.assignedTo !== UNASSIGNED)
          return false;
        if (
          assignment !== "ALL" &&
          assignment !== "UNASSIGNED" &&
          t.assignedTo !== assignment
        )
          return false;
        return true;
      })
      .sort((a, b) => {
        // Newest activity first, but unresolved always above resolved.
        const ar = a.status === TicketStatus.RESOLVED ? 1 : 0;
        const br = b.status === TicketStatus.RESOLVED ? 1 : 0;
        if (ar !== br) return ar - br;
        return +new Date(b.updatedAt) - +new Date(a.updatedAt);
      });
  }, [tickets, category, priority, status, assignment]);

  // Resolve the selected ticket against live context state.
  const selectedTicket =
    tickets.find((t) => t.ticketId === selectedTicketId) ??
    visible[0] ??
    null;

  return (
    <div className="flex h-full flex-col animate-fade-in">
      {/* Hub header with live Open / Urgent badges */}
      <div className="flex items-center gap-3 border-b border-slate-800 px-5 py-3.5">
        <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-sky-500/10 text-sky-400">
          <Headset className="h-4.5 w-4.5" />
        </span>
        <div>
          <h1 className="text-base font-semibold text-slate-100">
            Helpdesk &amp; Communications Hub
          </h1>
          <p className="text-xs text-slate-500">
            Unified merchant support across the portfolio
          </p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <Badge tone="crimson" dot>
            {openCount} Open
          </Badge>
          <Badge tone="crimson">
            <ShieldAlert className="h-3 w-3" />
            {urgentCount} Urgent
          </Badge>
        </div>
      </div>

      {/* 3-column body */}
      <div className="flex min-h-0 flex-1">
        <FilterSidebar
          tickets={tickets}
          category={category}
          setCategory={setCategory}
          priority={priority}
          setPriority={setPriority}
          status={status}
          setStatus={setStatus}
          assignment={assignment}
          setAssignment={setAssignment}
        />

        {/* Center feed */}
        <div className="flex w-[360px] shrink-0 flex-col overflow-y-auto border-r border-slate-800">
          <div className="flex items-center justify-between border-b border-slate-800 px-4 py-2.5">
            <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Ticket Queue
            </span>
            <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[11px] tabular-nums text-slate-400">
              {visible.length}
            </span>
          </div>
          {visible.length === 0 ? (
            <div className="flex flex-1 flex-col items-center justify-center gap-2 p-8 text-center">
              <Inbox className="h-8 w-8 text-slate-700" />
              <p className="text-sm text-slate-400">
                No tickets match these filters.
              </p>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setCategory("ALL");
                  setPriority("ALL");
                  setStatus("ALL");
                  setAssignment("ALL");
                }}
              >
                Clear filters
              </Button>
            </div>
          ) : (
            visible.map((t) => (
              <TicketRow
                key={t.ticketId}
                ticket={t}
                merchantName={merchantName(t.merchantId)}
                active={selectedTicket?.ticketId === t.ticketId}
                onSelect={() => setSelectedTicketId(t.ticketId)}
              />
            ))
          )}
        </div>

        {/* Right conversation pane */}
        <ConversationPane
          ticket={selectedTicket}
          merchantName={
            selectedTicket ? merchantName(selectedTicket.merchantId) : ""
          }
        />
      </div>
    </div>
  );
}
