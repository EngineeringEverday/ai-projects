"use client";

/**
 * MerchVault — Selection Context
 * --------------------------------
 * Tracks which merchant is currently open in the detail workspace and the
 * dashboard's global search query. Kept separate from MerchantContext so that
 * navigation state and data state evolve independently. Persists across tab
 * views within the dashboard sub-layout.
 */

import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";

/** Top-level dashboard view. Portfolio is the merchant table/detail; helpdesk
 *  is the support communications hub. Both share the same dashboard shell. */
export type DashboardView = "portfolio" | "helpdesk";

/** Tabs the merchant detail workspace can be opened directly into. */
export type RequestedTab =
  | "overview"
  | "profile"
  | "kyc"
  | "documents"
  | "custom"
  | "audit"
  | "support";

interface SelectionContextValue {
  selectedId: string | null;
  selectMerchant: (id: string | null) => void;
  globalSearch: string;
  setGlobalSearch: (q: string) => void;

  /** Active top-level view within the dashboard shell. */
  view: DashboardView;
  setView: (v: DashboardView) => void;

  /**
   * A one-shot requested tab for the merchant detail workspace. The workspace
   * consumes it on mount/selection (e.g. the helpdesk “Link to KYC Profile”
   * macro teleports straight into a merchant’s Documents view) then clears it.
   */
  requestedTab: RequestedTab | null;
  setRequestedTab: (t: RequestedTab | null) => void;

  /** Convenience: jump to the portfolio, open a merchant, on a given tab. */
  openMerchantTab: (id: string, tab: RequestedTab) => void;
}

const SelectionContext = createContext<SelectionContextValue | undefined>(
  undefined
);

export function SelectionProvider({ children }: { children: ReactNode }) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [globalSearch, setGlobalSearch] = useState("");
  const [view, setView] = useState<DashboardView>("portfolio");
  const [requestedTab, setRequestedTab] = useState<RequestedTab | null>(null);

  const openMerchantTab = useCallback(
    (id: string, tab: RequestedTab) => {
      setView("portfolio");
      setSelectedId(id);
      setRequestedTab(tab);
    },
    []
  );

  const value = useMemo(
    () => ({
      selectedId,
      selectMerchant: setSelectedId,
      globalSearch,
      setGlobalSearch,
      view,
      setView,
      requestedTab,
      setRequestedTab,
      openMerchantTab,
    }),
    [selectedId, globalSearch, view, requestedTab, openMerchantTab]
  );

  return (
    <SelectionContext.Provider value={value}>
      {children}
    </SelectionContext.Provider>
  );
}

export function useSelection(): SelectionContextValue {
  const ctx = useContext(SelectionContext);
  if (!ctx) {
    throw new Error("useSelection must be used within a SelectionProvider");
  }
  return ctx;
}
