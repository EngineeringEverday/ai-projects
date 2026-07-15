# MerchVault — Merchant Intelligence Platform

An enterprise-grade internal **Operations & Compliance Dashboard** for **PayForge**, a
B2B payment gateway. MerchVault gives Compliance Officers, Risk Analysts, and Account
Managers a single surface to audit, review, and manage merchant accounts — covering KYC,
UBO screening, document workflows, risk tiering, custom metadata, a full audit trail, and
an integrated **Helpdesk & Communications Hub** for merchant support.

Built with **Next.js 15 (App Router)**, **TypeScript**, and **Tailwind CSS**, with
composable shadcn-style UI primitives and `lucide-react` icons.

---

## Execution

```bash
# 1. Install dependencies
npm install

# 2. Run the dev server (http://localhost:3000)
npm run dev

# 3. Production build + serve
npm run build
npm run start
```

The root route (`/`) redirects to `/dashboard`.

---

## Architecture

```
src/
├── types/
│   └── merchant.ts              # Strict domain types, enums, tone/label maps
├── data/
│   └── mockMerchants.ts         # 5 fully-populated merchant seeds (M001–M005)
├── context/
│   ├── MerchantContext.tsx      # In-memory data store + all simulated mutations
│   └── SelectionContext.tsx     # Navigation state (selected merchant, search)
├── lib/
│   └── utils.ts                 # cn(), currency/date formatters, id helper
├── components/
│   ├── ui.tsx                   # shadcn-style primitives (Card, Badge, Button…)
│   ├── Logo.tsx                 # Inline SVG wordmark
│   ├── HelpdeskWorkspace.tsx    # 3-column support hub (queue, thread, actions)
│   └── MerchantDetailWorkspace.tsx  # The 7-tab operational interface
└── app/
    ├── layout.tsx               # Root HTML shell (dark theme)
    ├── page.tsx                 # / → redirect to /dashboard
    └── dashboard/
        ├── layout.tsx           # 'use client' global fintech shell (nav, top bar)
        └── page.tsx             # Metrics cards + sortable/filterable merchant table
```

### Key architectural choices

- **Client isolation.** The dashboard sub-layout (`app/dashboard/layout.tsx`) and every
  interactive view are marked `'use client'`. The app performs deep in-memory state
  mutations — approving documents, overriding risk tiers and statuses, editing custom
  metadata — so the interactive tree lives entirely on the client while the root layout
  stays a server component.

- **Two-context separation.** `MerchantContext` owns the canonical merchant data and
  every mutation. `SelectionContext` owns navigation (which merchant is open, the global
  search query). Splitting them keeps data and view state independently testable and
  prevents navigation re-renders from invalidating data subscribers.

- **Single source of truth for state.** Both providers are mounted in the dashboard
  sub-layout, so state persists across tab switches and detail navigations within a
  session. Every mutation deep-clones immutably and **auto-writes a timestamped audit
  event**, which is why approving a document instantly appears at the top of the Audit Log
  timeline and updates the sidebar status dots and notifications widget.

- **Dependency-light UI.** Rather than pull the full shadcn/ui primitive library, the
  shadcn *aesthetic* is implemented directly with Tailwind in `components/ui.tsx`
  (`Card`, `Badge`, `Button`, `Input`, `Textarea`, `Toggle`, `Meter`, `Modal`, `Select`).
  The table mimics TanStack Table ergonomics (column model, sort direction, multi-field
  filtering) with a custom `useMemo` pipeline and zero external table dependency.

### Color grammar

A strict fintech palette communicates state at a glance:

| Tone        | Meaning                          |
| ----------- | -------------------------------- |
| **Slate**   | Neutral dense data, expired      |
| **Emerald** | Verified status / low risk       |
| **Amber**   | Pending actions / medium risk    |
| **Crimson** | High risk / flagged breaches     |

---

## The 5 Merchants

| ID   | Merchant              | Risk        | Posture                                                    |
| ---- | --------------------- | ----------- | ---------------------------------------------------------- |
| M001 | AetherTech Solutions  | Low         | High-volume SaaS, KYC L3, AML passed, 0% reserve           |
| M002 | Lumina Retail Group   | Medium      | Omnichannel retail, approved w/ EDD, cross-border GBP      |
| M003 | NovaEats              | Medium-High | Food delivery, KYC pending (director ID timeout)           |
| M004 | ForgeCraft Marketplace| High        | Creator platform, KYC approved, 88 bps chargebacks, PEP    |
| M005 | Pulse Fitness Studios | Medium      | Gym network, under review (re-submitted after rejection)   |

---

## Helpdesk & Communications Hub

A portfolio-wide support surface that unifies every merchant ticket in one place, plus a
per-merchant **Support & Tickets** tab (the 7th tab in the merchant workspace).

- **3-column hub** — a filter sidebar (Category / Assignment / Priority / Status with live
  counts), a center ticket queue, and a right-hand conversation pane that renders the full
  chronological thread.
- **Ticket model** — each ticket carries a category, priority, status, assignee, and a
  message thread. Seeded tickets cover KYC blockers, chargeback disputes, settlement
  delays, technical/API issues, and billing queries (TK-1092, TK-1104, TK-1108, TK-1115,
  TK-1121).
- **Public / Internal split-toggle** — staff can post a public reply (light-blue ground)
  or an internal staff note (soft amber ground, lock icon, `[INTERNAL ONLY: Hidden from
  Merchant]` microcopy). Internal notes are never confused with merchant-facing replies.
- **Persona sender emulation** — the active persona (Alex Rivera / Jordan Lee / Sam Okafor)
  attributes every post in real time; switching persona updates the composer immediately.
- **Smart Risk Actions** — one-click macros: *Escalate to Risk Team* (assigns Jordan Lee
  and bumps priority to Urgent), *Link to KYC Profile* (teleports into the merchant's
  Documents tab), and *Resolve & Approve KYC Doc* (resolves the ticket **and** approves its
  linked compliance document in a single action).
- **Live, refresh-free updates** — resolving a ticket, escalating, or approving a linked
  document instantly updates the sidebar Open/Urgent badges and document statuses via
  Tailwind color transitions, with no page reload.

The hub reuses the same `MerchantContext` store, so a ticket action (e.g. approving a
linked KYC document) propagates everywhere — the Documents tab, status dots, and audit log
all reflect it immediately.

---

## Product Design Spec

**For the Compliance Officer (Alex), the platform is built to quiet the fear of the
undetected gap.** A compliance officer's recurring anxiety is the obligation that slipped
through — an unreviewed document, a sanctions match nobody dispositioned, an EDD cycle
that lapsed. MerchVault answers this with a notifications widget that surfaces every
pending document and chargeback breach the moment a merchant detail view loads, a KYC tab
that renders UBO verification and sanctions posture as unmissable color-coded badges (PEP
flags included), and an **immutable audit log** that timestamps and attributes every
action. Because each mutation auto-writes an audit entry with the active persona as the
actor, Alex never has to wonder "who approved this and when" — the timeline answers it.
Manual overrides are deliberately gated behind a **mandatory reason code**, so the system
makes the defensible, examiner-ready choice the path of least resistance.

**For the Risk Analyst (Jordan), the platform is built to make exposure legible and
adjustable in real time.** A risk engineer lives in the tension between letting good
volume flow and containing tail loss. MerchVault renders that tension as instrumentation:
composite risk gauges, a **risk-point matrix** that decomposes the score into its
contributing factors (chargeback rate, MCC risk, cross-border exposure, PEP/sanctions),
and chargeback figures that shift from emerald to amber to crimson as basis points climb
toward program thresholds. The rolling-reserve slider lets Jordan tune protection from 0%
to the 10% program cap and see the reserve-coverage gauge respond instantly — every
adjustment captured in the audit trail. The portfolio table's sort and filter controls
let Jordan triage the entire book by risk tier or chargeback load in seconds, turning a
spreadsheet exercise into a glanceable workflow.

**For the Account Manager (Sam), the platform is built to remove friction between a
merchant's needs and the controls that govern them.** An account manager's anxiety is
being the last to know — a merchant escalating about a held payout while the AM scrambles
to understand why. MerchVault gives Sam a complete, structural view of each account:
editable business-identity fields, masked settlement rails, processing caps, and a custom
metadata registry rendered as an editable JSON-style tree where operational levers
(`payout_hold_days`, `instant_payout_enabled`, `chargeback_alert_threshold_bps`) are
visible and adjustable. Rapid onboarding toggles on the Overview tab let Sam flip account
behaviors without leaving the page, and the persona switcher means the same workspace
adapts its attribution as responsibilities hand off between compliance, risk, and account
management — one shared source of truth, three points of view. The Helpdesk Hub extends
this further: Sam fields merchant questions in the conversation pane, Jordan picks up
escalated risk tickets, and Alex closes KYC blockers by resolving a ticket and approving
the linked document in one move — each action attributed to the acting persona and mirrored
across the rest of the platform.

---

## License

Internal use only — PayForge Compliance Suite v1.0.
