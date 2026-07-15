/** MerchVault wordmark + vault-shard glyph (inline SVG, currentColor). */
export function Logo({ className }: { className?: string }) {
  return (
    <div className={className}>
      <span className="inline-flex items-center gap-2">
        <svg
          width="26"
          height="26"
          viewBox="0 0 32 32"
          fill="none"
          aria-label="MerchVault logo"
          className="text-sky-400"
        >
          <rect
            x="3"
            y="3"
            width="26"
            height="26"
            rx="7"
            stroke="currentColor"
            strokeWidth="2"
          />
          <path
            d="M16 8L22 16L16 24L10 16L16 8Z"
            fill="currentColor"
            fillOpacity="0.18"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinejoin="round"
          />
          <circle cx="16" cy="16" r="2.4" fill="currentColor" />
        </svg>
        <span className="text-base font-semibold tracking-tight text-slate-100">
          Merch<span className="text-sky-400">Vault</span>
        </span>
      </span>
    </div>
  );
}
