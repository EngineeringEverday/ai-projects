"use client";

/**
 * MerchVault — Merchant State Context
 * -------------------------------------
 * Single in-memory store for the operations dashboard. All simulated mutations
 * (approving/rejecting documents, overriding risk tiers & statuses, editing
 * custom metadata, toggling onboarding flags) flow through this provider so
 * that state persists across tab views and detail navigations within a session.
 *
 * Every mutation also writes a corresponding entry into the merchant's audit
 * log so the Audit Log tab reflects analytical footprints in real time.
 */

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
} from "react";
import type { ReactNode } from "react";
import { MOCK_MERCHANTS, MOCK_TICKETS } from "@/data/mockMerchants";
import {
  AuditEvent,
  CustomField,
  DocStatus,
  Merchant,
  MerchantStatus,
  Persona,
  RiskTier,
  SupportTicket,
  ThreadMessage,
  TicketPriority,
  TicketStatus,
} from "@/types/merchant";
import { makeId } from "@/lib/utils";

/* ------------------------------------------------------------------ */
/* Context Shape                                                       */
/* ------------------------------------------------------------------ */

interface MerchantContextValue {
  merchants: Merchant[];
  activePersona: Persona;
  setActivePersona: (persona: Persona) => void;
  getMerchant: (id: string) => Merchant | undefined;

  /** Approve or reject a compliance document, with optional reviewer comment. */
  setDocumentStatus: (
    merchantId: string,
    documentId: string,
    status: DocStatus,
    comment?: string
  ) => void;

  /** Override a merchant's composite risk tier with a mandatory reason code. */
  overrideRiskTier: (
    merchantId: string,
    tier: RiskTier,
    reason: string
  ) => void;

  /** Override a merchant's lifecycle status with a mandatory reason code. */
  overrideStatus: (
    merchantId: string,
    status: MerchantStatus,
    reason: string
  ) => void;

  /** Update an existing custom metadata field's value. */
  updateCustomField: (
    merchantId: string,
    key: string,
    value: string | number | boolean
  ) => void;

  /** Add a new custom metadata tag. */
  addCustomField: (merchantId: string, field: CustomField) => void;

  /** Remove a custom metadata tag. */
  removeCustomField: (merchantId: string, key: string) => void;

  /** Adjust the rolling reserve percentage (0–10) from the Overview toggles. */
  setRollingReserve: (merchantId: string, pct: number) => void;

  /* ----------------------------- Helpdesk ----------------------------- */

  /** All support tickets across the portfolio. */
  tickets: SupportTicket[];

  /** Tickets belonging to a single merchant, newest activity first. */
  getMerchantTickets: (merchantId: string) => SupportTicket[];

  /**
   * Post a reply to a ticket as the active persona. `isInternalNote` toggles
   * between a client-facing Public Message and an Internal Staff Note.
   */
  postTicketReply: (
    ticketId: string,
    body: string,
    isInternalNote: boolean
  ) => void;

  /** Transition a ticket’s lifecycle status. */
  setTicketStatus: (ticketId: string, status: TicketStatus) => void;

  /** Change a ticket’s priority. */
  setTicketPriority: (ticketId: string, priority: TicketPriority) => void;

  /** Assign (or reassign) a ticket to a persona display name. */
  assignTicket: (ticketId: string, assignee: string) => void;

  /**
   * Smart Risk Action — escalate to the Risk team: assigns to Jordan Lee,
   * bumps priority to Urgent, and posts an internal escalation note.
   */
  escalateToRisk: (ticketId: string) => void;

  /**
   * Resolve a ticket. When the ticket is linked to a blocked KYC document,
   * optionally approve that document in the same action (the “approve pending
   * KYC doc” shortcut surfaced on resolution).
   */
  resolveTicket: (ticketId: string, approveLinkedDoc?: boolean) => void;
}

const MerchantContext = createContext<MerchantContextValue | undefined>(
  undefined
);

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

/** Persona id → display name used for audit attribution. */
const PERSONA_NAME: Record<Persona, string> = {
  ALEX: "Alex Rivera",
  JORDAN: "Jordan Lee",
  SAM: "Sam Okafor",
};

/** The Risk team owner that “Escalate to Risk Team” assigns tickets to. */
const RISK_TEAM_OWNER = "Jordan Lee";

/** Build a fresh ticket thread message. */
function makeMessage(
  sender: string,
  body: string,
  isInternalNote: boolean
): ThreadMessage {
  return {
    id: makeId("MSG"),
    sender,
    fromStaff: true,
    timestamp: new Date().toISOString(),
    messageBody: body,
    isInternalNote,
  };
}

/** Build a fresh audit event prepended to a merchant's log. */
function makeAudit(
  actor: string,
  action: string,
  detail: string,
  category: AuditEvent["category"]
): AuditEvent {
  return {
    id: makeId("AL"),
    timestamp: new Date().toISOString(),
    actor,
    action,
    detail,
    category,
  };
}

/* ------------------------------------------------------------------ */
/* Provider                                                            */
/* ------------------------------------------------------------------ */

export function MerchantProvider({ children }: { children: ReactNode }) {
  // Deep clone the seed so mutations never touch the original module data.
  const [merchants, setMerchants] = useState<Merchant[]>(() =>
    JSON.parse(JSON.stringify(MOCK_MERCHANTS))
  );
  const [activePersona, setActivePersona] = useState<Persona>("ALEX");
  // Deep clone the ticket seed so reply/status mutations never touch module data.
  const [tickets, setTickets] = useState<SupportTicket[]>(() =>
    JSON.parse(JSON.stringify(MOCK_TICKETS))
  );

  const actor = PERSONA_NAME[activePersona];

  /** Functional updater that maps over a single merchant by id. */
  const mutateMerchant = useCallback(
    (merchantId: string, fn: (m: Merchant) => Merchant) => {
      setMerchants((prev) =>
        prev.map((m) => (m.id === merchantId ? fn(m) : m))
      );
    },
    []
  );

  const getMerchant = useCallback(
    (id: string) => merchants.find((m) => m.id === id),
    [merchants]
  );

  const setDocumentStatus = useCallback<
    MerchantContextValue["setDocumentStatus"]
  >(
    (merchantId, documentId, status, comment) => {
      mutateMerchant(merchantId, (m) => {
        const doc = m.documents.find((d) => d.id === documentId);
        const docName = doc?.name ?? documentId;
        const verb = status === DocStatus.APPROVED ? "Approved" : "Rejected";
        return {
          ...m,
          documents: m.documents.map((d) =>
            d.id === documentId
              ? {
                  ...d,
                  status,
                  reviewedBy: actor,
                  reviewedAt: new Date().toISOString(),
                  comment: comment ?? d.comment,
                }
              : d
          ),
          auditLog: [
            makeAudit(
              actor,
              `Document ${verb}`,
              `${docName}${comment ? ` — "${comment}"` : ""}`,
              "DOCUMENT"
            ),
            ...m.auditLog,
          ],
        };
      });
    },
    [actor, mutateMerchant]
  );

  const overrideRiskTier = useCallback<
    MerchantContextValue["overrideRiskTier"]
  >(
    (merchantId, tier, reason) => {
      mutateMerchant(merchantId, (m) => ({
        ...m,
        riskTier: tier,
        auditLog: [
          makeAudit(
            actor,
            "Risk Tier Override",
            `Tier manually set to ${tier}. Reason code: ${reason}.`,
            "OVERRIDE"
          ),
          ...m.auditLog,
        ],
      }));
    },
    [actor, mutateMerchant]
  );

  const overrideStatus = useCallback<MerchantContextValue["overrideStatus"]>(
    (merchantId, status, reason) => {
      mutateMerchant(merchantId, (m) => ({
        ...m,
        status,
        auditLog: [
          makeAudit(
            actor,
            "Status Override",
            `Status manually set to ${status}. Reason code: ${reason}.`,
            "OVERRIDE"
          ),
          ...m.auditLog,
        ],
      }));
    },
    [actor, mutateMerchant]
  );

  const updateCustomField = useCallback<
    MerchantContextValue["updateCustomField"]
  >(
    (merchantId, key, value) => {
      mutateMerchant(merchantId, (m) => ({
        ...m,
        customFields: m.customFields.map((f) =>
          f.key === key ? { ...f, value } : f
        ),
        auditLog: [
          makeAudit(
            actor,
            "Metadata Updated",
            `Field "${key}" set to "${String(value)}".`,
            "METADATA"
          ),
          ...m.auditLog,
        ],
      }));
    },
    [actor, mutateMerchant]
  );

  const addCustomField = useCallback<MerchantContextValue["addCustomField"]>(
    (merchantId, field) => {
      mutateMerchant(merchantId, (m) => {
        if (m.customFields.some((f) => f.key === field.key)) return m;
        return {
          ...m,
          customFields: [...m.customFields, field],
          auditLog: [
            makeAudit(
              actor,
              "Metadata Tag Added",
              `Added "${field.key}" = "${String(field.value)}".`,
              "METADATA"
            ),
            ...m.auditLog,
          ],
        };
      });
    },
    [actor, mutateMerchant]
  );

  const removeCustomField = useCallback<
    MerchantContextValue["removeCustomField"]
  >(
    (merchantId, key) => {
      mutateMerchant(merchantId, (m) => ({
        ...m,
        customFields: m.customFields.filter((f) => f.key !== key),
        auditLog: [
          makeAudit(
            actor,
            "Metadata Tag Removed",
            `Removed field "${key}".`,
            "METADATA"
          ),
          ...m.auditLog,
        ],
      }));
    },
    [actor, mutateMerchant]
  );

  const setRollingReserve = useCallback<
    MerchantContextValue["setRollingReserve"]
  >(
    (merchantId, pct) => {
      const clamped = Math.max(0, Math.min(10, pct));
      mutateMerchant(merchantId, (m) => ({
        ...m,
        financialProfile: {
          ...m.financialProfile,
          rollingReservePct: clamped,
        },
        auditLog: [
          makeAudit(
            actor,
            "Rolling Reserve Changed",
            `Rolling reserve set to ${clamped}%.`,
            "RISK"
          ),
          ...m.auditLog,
        ],
      }));
    },
    [actor, mutateMerchant]
  );

  /* ------------------------------------------------------------------ */
  /* Helpdesk mutations                                                  */
  /* ------------------------------------------------------------------ */

  /** Functional updater that maps over a single ticket by id, stamping it. */
  const mutateTicket = useCallback(
    (ticketId: string, fn: (t: SupportTicket) => SupportTicket) => {
      setTickets((prev) =>
        prev.map((t) =>
          t.ticketId === ticketId
            ? { ...fn(t), updatedAt: new Date().toISOString() }
            : t
        )
      );
    },
    []
  );

  const getMerchantTickets = useCallback(
    (merchantId: string) =>
      tickets
        .filter((t) => t.merchantId === merchantId)
        .sort((a, b) => +new Date(b.updatedAt) - +new Date(a.updatedAt)),
    [tickets]
  );

  const postTicketReply = useCallback<
    MerchantContextValue["postTicketReply"]
  >(
    (ticketId, body, isInternalNote) => {
      const trimmed = body.trim();
      if (!trimmed) return;
      mutateTicket(ticketId, (t) => ({
        ...t,
        thread: [...t.thread, makeMessage(actor, trimmed, isInternalNote)],
        // A public reply moves an open ticket into active handling.
        status:
          !isInternalNote && t.status === TicketStatus.OPEN
            ? TicketStatus.IN_PROGRESS
            : t.status,
      }));
    },
    [actor, mutateTicket]
  );

  const setTicketStatus = useCallback<
    MerchantContextValue["setTicketStatus"]
  >(
    (ticketId, status) => {
      mutateTicket(ticketId, (t) => ({ ...t, status }));
    },
    [mutateTicket]
  );

  const setTicketPriority = useCallback<
    MerchantContextValue["setTicketPriority"]
  >(
    (ticketId, priority) => {
      mutateTicket(ticketId, (t) => ({ ...t, priority }));
    },
    [mutateTicket]
  );

  const assignTicket = useCallback<MerchantContextValue["assignTicket"]>(
    (ticketId, assignee) => {
      mutateTicket(ticketId, (t) => ({ ...t, assignedTo: assignee }));
    },
    [mutateTicket]
  );

  const escalateToRisk = useCallback<MerchantContextValue["escalateToRisk"]>(
    (ticketId) => {
      mutateTicket(ticketId, (t) => ({
        ...t,
        assignedTo: RISK_TEAM_OWNER,
        priority: TicketPriority.URGENT,
        status:
          t.status === TicketStatus.RESOLVED
            ? TicketStatus.IN_PROGRESS
            : t.status,
        thread: [
          ...t.thread,
          makeMessage(
            actor,
            `Escalated to the Risk Team. Reassigned to ${RISK_TEAM_OWNER} and priority raised to Urgent for expedited review.`,
            true
          ),
        ],
      }));
    },
    [actor, mutateTicket]
  );

  const resolveTicket = useCallback<MerchantContextValue["resolveTicket"]>(
    (ticketId, approveLinkedDoc) => {
      const ticket = tickets.find((t) => t.ticketId === ticketId);
      // If linked to a blocked KYC doc, approve it as part of resolution.
      if (approveLinkedDoc && ticket?.linkedDocumentId) {
        setDocumentStatus(
          ticket.merchantId,
          ticket.linkedDocumentId,
          DocStatus.APPROVED,
          `Approved while resolving support ticket ${ticketId}.`
        );
      }
      mutateTicket(ticketId, (t) => ({
        ...t,
        status: TicketStatus.RESOLVED,
        thread:
          approveLinkedDoc && t.linkedDocumentId
            ? [
                ...t.thread,
                makeMessage(
                  actor,
                  "Linked KYC document approved and ticket resolved. Payouts will be released on the next settlement run.",
                  false
                ),
              ]
            : t.thread,
      }));
    },
    [actor, mutateTicket, setDocumentStatus, tickets]
  );

  const value = useMemo<MerchantContextValue>(
    () => ({
      merchants,
      activePersona,
      setActivePersona,
      getMerchant,
      setDocumentStatus,
      overrideRiskTier,
      overrideStatus,
      updateCustomField,
      addCustomField,
      removeCustomField,
      setRollingReserve,
      tickets,
      getMerchantTickets,
      postTicketReply,
      setTicketStatus,
      setTicketPriority,
      assignTicket,
      escalateToRisk,
      resolveTicket,
    }),
    [
      merchants,
      activePersona,
      getMerchant,
      setDocumentStatus,
      overrideRiskTier,
      overrideStatus,
      updateCustomField,
      addCustomField,
      removeCustomField,
      setRollingReserve,
      tickets,
      getMerchantTickets,
      postTicketReply,
      setTicketStatus,
      setTicketPriority,
      assignTicket,
      escalateToRisk,
      resolveTicket,
    ]
  );

  return (
    <MerchantContext.Provider value={value}>
      {children}
    </MerchantContext.Provider>
  );
}

/** Hook to consume the merchant store. Throws if used outside the provider. */
export function useMerchants(): MerchantContextValue {
  const ctx = useContext(MerchantContext);
  if (!ctx) {
    throw new Error("useMerchants must be used within a MerchantProvider");
  }
  return ctx;
}
