import { useRef, type ReactNode } from "react";

/** Perspective tilt that follows the pointer. Wrap anything card-shaped. */
export function Tilt({ children, max = 6, className = "" }: { children: ReactNode; max?: number; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);

  function onMove(e: React.PointerEvent<HTMLDivElement>) {
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width - 0.5;
    const y = (e.clientY - r.top) / r.height - 0.5;
    el.style.transform = `perspective(1200px) rotateX(${-y * max}deg) rotateY(${x * max}deg) translateZ(0)`;
    el.style.setProperty("--glare-x", `${(x + 0.5) * 100}%`);
    el.style.setProperty("--glare-y", `${(y + 0.5) * 100}%`);
  }

  function reset() {
    const el = ref.current;
    if (el) el.style.transform = "perspective(1200px) rotateX(0deg) rotateY(0deg)";
  }

  return (
    <div ref={ref} className={`mkTilt ${className}`} onPointerMove={onMove} onPointerLeave={reset}>
      {children}
      <span className="mkGlare" aria-hidden="true" />
    </div>
  );
}
