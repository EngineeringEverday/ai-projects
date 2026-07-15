/**
 * MerchVault — Core Domain Types
 * ---------------------------------
 * Strict TypeScript contracts for the PayForge Merchant Intelligence Platform.
 * Every entity an analyst touches — merchants, UBOs, documents, audit events —
 * is modeled here as the single source of truth shared across the app.
 */

/* ------------------------------------------------------------------ */
/* Enums & Literal Unions                                              */
/* ------------------------------------------------------------------ */

/** Composite risk classification surfaced across the platform. */
export enum RiskTier {
  LOW = "LOW",
  MEDIUM = "MEDIUM",
  MEDIUM_HIGH = "MEDIUM_HIGH",
  HIGH = "HIGH",
}

/** Top-level merchant onboarding / lifecycle state. */
export enum MerchantStatus {
  APPROVED = "APPROVED",
  PENDING = "PENDING",
  UNDER_REVIEW = "UNDER_REVIEW",
  SUSPENDED = "SUSPENDED",
  REJECTED = "REJECTED",
}

/** KYC verification depth as defined by PayForge's tiered program. */
export enum KycLevel {
  LEVEL_1 = "LEVEL_1",
  LEVEL_2 = "LEVEL_2",
  LEVEL_3 = "LEVEL_3",
}

/** Outcome of a KYC review cycle. */
export enum KycStatus {
  APPROVED = "APPROVED",
  PENDING = "PENDING",
  ENHANCED_DUE_DILIGENCE = "ENHANCED_DUE_DILIGENCE",
  REJECTED = "REJECTED",
}

/** Automated AML transaction-monitoring result. */
export enum AmlResult {
  PASSED = "PASSED",
  REVIEW = "REVIEW",
  FAILED = "FAILED",
  NOT_RUN = "NOT_RUN",
}

/** Document workflow state — drives the Documents tab approve/reject flow. */
export enum DocStatus {
  APPROVED = "APPROVED",
  PENDING_REVIEW = "PENDING_REVIEW",
  REJECTED = "REJECTED",
  EXPIRED = "EXPIRED",
}

/** Sanctions / watchlist screening outcome for a beneficial owner. */
export enum SanctionsFlag {
  CLEAR = "CLEAR",
  POTENTIAL_MATCH = "POTENTIAL_MATCH",
  CONFIRMED_HIT = "CONFIRMED_HIT",
  PENDING = "PENDING",
}

/** UBO identity verification posture. */
export enum VerificationStatus {
  VERIFIED = "VERIFIED",
  PENDING = "PENDING",
  FAILED = "FAILED",
  TIMEOUT = "TIMEOUT",
}

/** Categories of compliance artifact merchants submit. */
export type DocumentCategory =
  | "INCORPORATION"
  | "OWNERSHIP"
  | "BANKING"
  | "TAX"
  | "PROCESSING_HISTORY"
  | "AML_POLICY"
  | "LICENSE"
  | "IDENTITY";

/** Internal personas using the dashboard (persona switcher). */
export type Persona = "ALEX" | "JORDAN" | "SAM";

/** Datatype hint for the editable custom-metadata playground. */
export type MetaValueType = "string" | "number" | "boolean";

/* ------------------------------------------------------------------ */
/* Sub-Entities                                                        */
/* ------------------------------------------------------------------ */

/** Ultimate Beneficial Owner record with screening posture. */
export interface UBO {
  id: string;
  fullName: string;
  role: string;
  ownershipPct: number;
  nationality: string;
  dateOfBirth: string; // ISO date
  verification: VerificationStatus;
  sanctions: SanctionsFlag;
  pep: boolean; // politically exposed person
  notes?: string;
}

/** A single compliance document in the review queue. */
export interface ComplianceDocument {
  id: string;
  name: string;
  category: DocumentCategory;
  status: DocStatus;
  uploadedAt: string; // ISO datetime
  reviewedBy?: string;
  reviewedAt?: string; // ISO datetime
  fileType: "PDF" | "PNG" | "JPG" | "XLSX";
  sizeKb: number;
  comment?: string; // reviewer rejection / approval note
}

/** Structured legal & business identity of the merchant. */
export interface BusinessProfile {
  legalEntityType: string;
  dba: string;
  ein: string; // EIN / Tax ID
  processingDescriptor: string;
  mccCode: string;
  mccDescription: string;
  incorporationState: string;
  incorporationDate: string; // ISO date
  website: string;
  supportEmail: string;
  supportPhone: string;
}

/** Masked settlement rail (bank account) used for payouts. */
export interface SettlementRail {
  id: string;
  bankName: string;
  accountMask: string; // e.g. ****4821
  routingMask: string;
  currency: string;
  primary: boolean;
}

/** Financial / processing economics of the account. */
export interface FinancialProfile {
  monthlyVolumeUsd: number;
  avgTicketUsd: number;
  rollingReservePct: number; // 0 - 10
  chargebackBps: number; // basis points
  lifetimeVolumeUsd: number;
  settlementRails: SettlementRail[];
}

/** A single editable custom metadata tag. */
export interface CustomField {
  key: string;
  value: string | number | boolean;
  type: MetaValueType;
}

/** Chronological audit footprint entry. */
export interface AuditEvent {
  id: string;
  timestamp: string; // ISO datetime
  actor: string;
  action: string;
  detail: string;
  category: "RISK" | "KYC" | "DOCUMENT" | "OVERRIDE" | "METADATA" | "SYSTEM";
}

/* ------------------------------------------------------------------ */
/* Root Aggregate                                                      */
/* ------------------------------------------------------------------ */

/** The full merchant aggregate persisted in context state. */
export interface Merchant {
  id: string;
  legalName: string;
  riskTier: RiskTier;
  status: MerchantStatus;
  kycLevel: KycLevel;
  kycStatus: KycStatus;
  amlResult: AmlResult;
  riskScore: number; // 0 - 100 composite
  crossBorder: boolean;
  onboardedAt: string; // ISO date
  accountManager: string;
  businessProfile: BusinessProfile;
  financialProfile: FinancialProfile;
  ubos: UBO[];
  documents: ComplianceDocument[];
  customFields: CustomField[];
  auditLog: AuditEvent[];
}

/* ------------------------------------------------------------------ */
/* Display Helpers                                                     */
/* ------------------------------------------------------------------ */

/** Tailwind color grammar tokens keyed by semantic intent. */
export type ToneKey = "slate" | "emerald" | "amber" | "crimson";

/** Maps a risk tier to the fintech color grammar tone. */
export const RISK_TONE: Record<RiskTier, ToneKey> = {
  [RiskTier.LOW]: "emerald",
  [RiskTier.MEDIUM]: "amber",
  [RiskTier.MEDIUM_HIGH]: "amber",
  [RiskTier.HIGH]: "crimson",
};

/** Maps a merchant status to a color grammar tone. */
export const STATUS_TONE: Record<MerchantStatus, ToneKey> = {
  [MerchantStatus.APPROVED]: "emerald",
  [MerchantStatus.PENDING]: "amber",
  [MerchantStatus.UNDER_REVIEW]: "amber",
  [MerchantStatus.SUSPENDED]: "crimson",
  [MerchantStatus.REJECTED]: "crimson",
};

/** Maps a document status to a color grammar tone. */
export const DOC_TONE: Record<DocStatus, ToneKey> = {
  [DocStatus.APPROVED]: "emerald",
  [DocStatus.PENDING_REVIEW]: "amber",
  [DocStatus.REJECTED]: "crimson",
  [DocStatus.EXPIRED]: "slate",
};

/** Human-readable labels for enum-ish values. */
export const RISK_LABEL: Record<RiskTier, string> = {
  [RiskTier.LOW]: "Low Risk",
  [RiskTier.MEDIUM]: "Medium Risk",
  [RiskTier.MEDIUM_HIGH]: "Medium-High Risk",
  [RiskTier.HIGH]: "High Risk",
};

export const STATUS_LABEL: Record<MerchantStatus, string> = {
  [MerchantStatus.APPROVED]: "Approved",
  [MerchantStatus.PENDING]: "Pending",
  [MerchantStatus.UNDER_REVIEW]: "Under Review",
  [MerchantStatus.SUSPENDED]: "Suspended",
  [MerchantStatus.REJECTED]: "Rejected",
};

export const KYC_STATUS_LABEL: Record<KycStatus, string> = {
  [KycStatus.APPROVED]: "Approved",
  [KycStatus.PENDING]: "Pending",
  [KycStatus.ENHANCED_DUE_DILIGENCE]: "Enhanced Due Diligence",
  [KycStatus.REJECTED]: "Rejected",
};

/** Persona display metadata for the top-bar switcher. */
export interface PersonaMeta {
  id: Persona;
  name: string;
  role: string;
  initials: string;
}

export const PERSONAS: PersonaMeta[] = [
  { id: "ALEX", name: "Alex Rivera", role: "Compliance Officer", initials: "AR" },
  { id: "JORDAN", name: "Jordan Lee", role: "Risk Analyst", initials: "JL" },
  { id: "SAM", name: "Sam Okafor", role: "Account Manager", initials: "SO" },
];

/* ================================================================== */
/* Merchant Helpdesk & Communications Hub                              */
/* ------------------------------------------------------------------ */
/* Support tickets are first-class entities linked to a merchant (FK). */
/* Each ticket carries a chronological message thread that interleaves */
/* client-facing public replies with internal-only staff notes.        */
/* ================================================================== */

/** Functional grouping for a support ticket — drives queue triage. */
export enum TicketCategory {
  KYC_BLOCKER = "KYC_BLOCKER",
  CHARGEBACK_DISPUTE = "CHARGEBACK_DISPUTE",
  SETTLEMENT_DELAY = "SETTLEMENT_DELAY",
  TECHNICAL_API = "TECHNICAL_API",
  BILLING_QUERY = "BILLING_QUERY",
}

/** Operational urgency of a support ticket. */
export enum TicketPriority {
  URGENT = "URGENT",
  HIGH = "HIGH",
  MEDIUM = "MEDIUM",
  LOW = "LOW",
}

/** Lifecycle state of a support ticket. */
export enum TicketStatus {
  OPEN = "OPEN",
  IN_PROGRESS = "IN_PROGRESS",
  PENDING_MERCHANT = "PENDING_MERCHANT",
  RESOLVED = "RESOLVED",
}

/** Sentinel for an unassigned ticket. */
export const UNASSIGNED = "Unassigned";

/** A single message in a ticket thread — public reply or internal note. */
export interface ThreadMessage {
  id: string;
  /** Display name of the author (merchant contact or internal persona). */
  sender: string;
  /** True when the author is an internal staff member (not the merchant). */
  fromStaff: boolean;
  timestamp: string; // ISO datetime
  messageBody: string;
  /** Internal notes are hidden from the merchant — soft amber, lock icon. */
  isInternalNote: boolean;
}

/** A merchant support ticket with a full conversation thread. */
export interface SupportTicket {
  ticketId: string; // e.g. "TK-1104"
  merchantId: string; // FK → Merchant.id (M001–M005)
  subject: string;
  category: TicketCategory;
  priority: TicketPriority;
  status: TicketStatus;
  /** Persona display name owning the ticket, or UNASSIGNED. */
  assignedTo: string;
  createdAt: string; // ISO datetime
  updatedAt: string; // ISO datetime
  thread: ThreadMessage[];
  /**
   * Optional shortcut: a merchant document this ticket is blocked on. When
   * present, resolving the ticket offers a one-click approve of that doc and
   * a teleport into the merchant's Documents view.
   */
  linkedDocumentId?: string;
}

/* ------------------------------------------------------------------ */
/* Ticket Display Helpers                                              */
/* ------------------------------------------------------------------ */

/** Maps ticket priority → fintech color grammar tone. */
export const TICKET_PRIORITY_TONE: Record<TicketPriority, ToneKey> = {
  [TicketPriority.URGENT]: "crimson",
  [TicketPriority.HIGH]: "crimson",
  [TicketPriority.MEDIUM]: "amber",
  [TicketPriority.LOW]: "emerald",
};

/** Maps ticket status → fintech color grammar tone. */
export const TICKET_STATUS_TONE: Record<TicketStatus, ToneKey> = {
  [TicketStatus.OPEN]: "crimson",
  [TicketStatus.IN_PROGRESS]: "amber",
  [TicketStatus.PENDING_MERCHANT]: "amber",
  [TicketStatus.RESOLVED]: "emerald",
};

export const TICKET_PRIORITY_LABEL: Record<TicketPriority, string> = {
  [TicketPriority.URGENT]: "Urgent",
  [TicketPriority.HIGH]: "High",
  [TicketPriority.MEDIUM]: "Medium",
  [TicketPriority.LOW]: "Low",
};

export const TICKET_STATUS_LABEL: Record<TicketStatus, string> = {
  [TicketStatus.OPEN]: "Open",
  [TicketStatus.IN_PROGRESS]: "In Progress",
  [TicketStatus.PENDING_MERCHANT]: "Pending Merchant",
  [TicketStatus.RESOLVED]: "Resolved",
};

export const TICKET_CATEGORY_LABEL: Record<TicketCategory, string> = {
  [TicketCategory.KYC_BLOCKER]: "KYC Blocker",
  [TicketCategory.CHARGEBACK_DISPUTE]: "Chargeback Dispute",
  [TicketCategory.SETTLEMENT_DELAY]: "Settlement Delay",
  [TicketCategory.TECHNICAL_API]: "Technical / API",
  [TicketCategory.BILLING_QUERY]: "Billing Query",
};
