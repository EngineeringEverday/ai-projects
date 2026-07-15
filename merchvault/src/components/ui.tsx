"use client";

/**
 * MerchVault — UI Primitives
 * ----------------------------
 * Lightweight, composable Tailwind components matching the shadcn/ui aesthetic
 * without pulling the full primitive library. Implements the fintech color
 * grammar: slate (neutral), emerald (verified/low), amber (pending/medium),
 * crimson (high/flagged).
 */

import {
  ButtonHTMLAttributes,
  HTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  TextareaHTMLAttributes,
  forwardRef,
  useEffect,
} from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ToneKey } from "@/types/merchant";

/* ------------------------------------------------------------------ */
/* Tone tokens                                                         */
/* ------------------------------------------------------------------ */

export const TONE_BADGE: Record<ToneKey, string> = {
  slate: "bg-slate-700/40 text-slate-300 ring-1 ring-inset ring-slate-600/50",
  emerald:
    "bg-emerald-500/10 text-emerald-300 ring-1 ring-inset ring-emerald-500/30",
  amber: "bg-amber-500/10 text-amber-300 ring-1 ring-inset ring-amber-500/30",
  crimson: "bg-rose-500/10 text-rose-300 ring-1 ring-inset ring-rose-500/30",
};

export const TONE_DOT: Record<ToneKey, string> = {
  slate: "bg-slate-400",
  emerald: "bg-emerald-400",
  amber: "bg-amber-400",
  crimson: "bg-rose-400",
};

export const TONE_BAR: Record<ToneKey, string> = {
  slate: "bg-slate-400",
  emerald: "bg-emerald-500",
  amber: "bg-amber-500",
  crimson: "bg-rose-500",
};

export const TONE_TEXT: Record<ToneKey, string> = {
  slate: "text-slate-300",
  emerald: "text-emerald-400",
  amber: "text-amber-400",
  crimson: "text-rose-400",
};

/* ------------------------------------------------------------------ */
/* Card                                                                */
/* ------------------------------------------------------------------ */

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "rounded-xl border border-slate-800 bg-slate-900/60 shadow-sm",
        className
      )}
      {...props}
    />
  );
}

export function CardHeader({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("flex flex-col gap-1 px-5 pt-4 pb-3", className)}
      {...props}
    />
  );
}

export function CardTitle({
  className,
  ...props
}: HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3
      className={cn(
        "text-sm font-semibold tracking-tight text-slate-100",
        className
      )}
      {...props}
    />
  );
}

export function CardContent({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("px-5 pb-5", className)} {...props} />;
}

/* ------------------------------------------------------------------ */
/* Badge                                                               */
/* ------------------------------------------------------------------ */

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: ToneKey;
  dot?: boolean;
}

export function Badge({
  tone = "slate",
  dot = false,
  className,
  children,
  ...props
}: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-xs font-medium",
        TONE_BADGE[tone],
        className
      )}
      {...props}
    >
      {dot && (
        <span className={cn("h-1.5 w-1.5 rounded-full", TONE_DOT[tone])} />
      )}
      {children}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* Button                                                              */
/* ------------------------------------------------------------------ */

type ButtonVariant =
  | "primary"
  | "secondary"
  | "ghost"
  | "outline"
  | "emerald"
  | "crimson"
  | "amber";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: "sm" | "md" | "icon";
}

const BUTTON_VARIANT: Record<ButtonVariant, string> = {
  primary:
    "bg-sky-500 text-white hover:bg-sky-400 focus-visible:ring-sky-400/50",
  secondary:
    "bg-slate-800 text-slate-100 hover:bg-slate-700 focus-visible:ring-slate-500/50",
  ghost:
    "bg-transparent text-slate-300 hover:bg-slate-800 hover:text-slate-100 focus-visible:ring-slate-500/40",
  outline:
    "border border-slate-700 bg-transparent text-slate-200 hover:bg-slate-800 focus-visible:ring-slate-500/40",
  emerald:
    "bg-emerald-500 text-white hover:bg-emerald-400 focus-visible:ring-emerald-400/50",
  crimson:
    "bg-rose-500 text-white hover:bg-rose-400 focus-visible:ring-rose-400/50",
  amber:
    "bg-amber-500 text-slate-950 hover:bg-amber-400 focus-visible:ring-amber-400/50",
};

const BUTTON_SIZE: Record<NonNullable<ButtonProps["size"]>, string> = {
  sm: "h-7 px-2.5 text-xs gap-1.5",
  md: "h-9 px-3.5 text-sm gap-2",
  icon: "h-8 w-8 p-0",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = "primary", size = "md", className, ...props }, ref) => (
    <button
      ref={ref}
      className={cn(
        "inline-flex items-center justify-center rounded-md font-medium transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 disabled:pointer-events-none disabled:opacity-50",
        BUTTON_VARIANT[variant],
        BUTTON_SIZE[size],
        className
      )}
      {...props}
    />
  )
);
Button.displayName = "Button";

/* ------------------------------------------------------------------ */
/* Input & Textarea                                                    */
/* ------------------------------------------------------------------ */

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "h-9 w-full rounded-md border border-slate-700 bg-slate-950/60 px-3 text-sm text-slate-100",
        "placeholder:text-slate-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/40 focus-visible:border-sky-600",
        className
      )}
      {...props}
    />
  )
);
Input.displayName = "Input";

export const Textarea = forwardRef<
  HTMLTextAreaElement,
  TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => (
  <textarea
    ref={ref}
    className={cn(
      "w-full rounded-md border border-slate-700 bg-slate-950/60 px-3 py-2 text-sm text-slate-100",
      "placeholder:text-slate-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/40 focus-visible:border-sky-600",
      className
    )}
    {...props}
  />
));
Textarea.displayName = "Textarea";

/* ------------------------------------------------------------------ */
/* Toggle Switch                                                       */
/* ------------------------------------------------------------------ */

interface ToggleProps {
  checked: boolean;
  onChange: (v: boolean) => void;
  label?: string;
  disabled?: boolean;
}

export function Toggle({ checked, onChange, label, disabled }: ToggleProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        "relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400/50 disabled:opacity-40",
        checked ? "bg-emerald-500" : "bg-slate-700"
      )}
    >
      <span
        className={cn(
          "inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform",
          checked ? "translate-x-4" : "translate-x-0.5"
        )}
      />
    </button>
  );
}

/* ------------------------------------------------------------------ */
/* Progress / Meter                                                    */
/* ------------------------------------------------------------------ */

export function Meter({
  value,
  max = 100,
  tone = "slate",
  className,
}: {
  value: number;
  max?: number;
  tone?: ToneKey;
  className?: string;
}) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div
      className={cn(
        "h-2 w-full overflow-hidden rounded-full bg-slate-800",
        className
      )}
    >
      <div
        className={cn("h-full rounded-full transition-all", TONE_BAR[tone])}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Modal / Dialog                                                      */
/* ------------------------------------------------------------------ */

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  description?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  size?: "md" | "lg";
}

export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  size = "md",
}: ModalProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-slate-950/70 backdrop-blur-sm animate-fade-in"
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        className={cn(
          "relative z-10 w-full overflow-hidden rounded-xl border border-slate-800 bg-slate-900 shadow-2xl animate-scale-in",
          size === "lg" ? "max-w-3xl" : "max-w-lg"
        )}
      >
        <div className="flex items-start justify-between border-b border-slate-800 px-5 py-4">
          <div>
            <h2 className="text-sm font-semibold text-slate-100">{title}</h2>
            {description && (
              <p className="mt-0.5 text-xs text-slate-400">{description}</p>
            )}
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="rounded-md p-1 text-slate-400 hover:bg-slate-800 hover:text-slate-100"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="px-5 py-4">{children}</div>
        {footer && (
          <div className="flex items-center justify-end gap-2 border-t border-slate-800 bg-slate-900/60 px-5 py-3">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Stat label / value helpers                                          */
/* ------------------------------------------------------------------ */

export function FieldRow({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-slate-800/60 py-2 last:border-0">
      <span className="text-xs font-medium uppercase tracking-wide text-slate-500">
        {label}
      </span>
      <span className="text-right text-sm text-slate-200">{children}</span>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Select                                                              */
/* ------------------------------------------------------------------ */

interface SelectProps
  extends React.SelectHTMLAttributes<HTMLSelectElement> {
  options: { value: string; label: string }[];
}

export function Select({ options, className, ...props }: SelectProps) {
  return (
    <select
      className={cn(
        "h-9 w-full rounded-md border border-slate-700 bg-slate-950/60 px-3 text-sm text-slate-100",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/40",
        className
      )}
      {...props}
    >
      {options.map((o) => (
        <option key={o.value} value={o.value} className="bg-slate-900">
          {o.label}
        </option>
      ))}
    </select>
  );
}
