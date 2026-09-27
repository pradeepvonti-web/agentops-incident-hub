/**
 * Restora's logo is its wordmark: "restora", lowercase, in the display face,
 * with the o in orange. `LogoMark` is the tile for places type cannot go —
 * favicon, home-screen icon, social image. public/logo.svg is the same tile.
 */
export function Logo({
  size = 22,
  tone = "dark",
  className = ""
}: {
  /** Cap height in px; the wordmark scales from it. */
  size?: number;
  /** Ink colour of the letters: dark on light surfaces, light on the sidebar. */
  tone?: "dark" | "light";
  className?: string;
}) {
  return (
    <span
      className={`logo logo-${tone} ${className}`}
      style={{ fontSize: size * 1.45 }}
      role="img"
      aria-label="Restora"
    >
      rest<span className="logoO">o</span>ra
    </span>
  );
}

export function LogoMark({ size = 28, className = "" }: { size?: number; className?: string }) {
  return (
    <svg
      className={`logoMark ${className}`}
      width={size}
      height={size}
      viewBox="0 0 64 64"
      role="img"
      aria-label="Restora"
    >
      <rect width="64" height="64" rx="16" fill="#1f8a4c" />
      <path d="M22 48V24" stroke="#ffffff" strokeWidth="8" strokeLinecap="round" />
      <path d="M22 30Q22 22 32 22Q40 22 42 26" fill="none" stroke="#ffffff" strokeWidth="8" strokeLinecap="round" />
      <circle cx="46" cy="46" r="6" fill="#f25533" />
    </svg>
  );
}
