import { useEffect, useRef, useState } from "react";

const CHAPTERS = [
  { at: 1.2, label: "Declare" },
  { at: 5.0, label: "Agent hypothesis" },
  { at: 6.4, label: "Actions" },
  { at: 8.6, label: "Monitoring" },
  { at: 10.2, label: "Customer update" }
];

/**
 * A rendered walkthrough of one incident, start to finish. Plays when it
 * scrolls into view, pauses when it leaves, and the chapter row seeks.
 */
export function DemoVideo({ onExpand }: { onExpand?: () => void }) {
  const video = useRef<HTMLVideoElement>(null);
  const [time, setTime] = useState(0);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    const v = video.current;
    if (!v) return;
    // React does not always write the `muted` attribute to the DOM, and
    // browsers only autoplay video that is muted at load time.
    v.muted = true;
    v.defaultMuted = true;

    let visible = false;
    const tryPlay = () => {
      if (visible && v.paused) v.play().catch(() => undefined);
    };
    const io = new IntersectionObserver(
      ([entry]) => {
        visible = entry.isIntersecting;
        if (visible) tryPlay();
        else v.pause();
      },
      { threshold: 0.25 }
    );
    io.observe(v);
    // Autoplay policies differ; any interaction is a second chance to start.
    window.addEventListener("scroll", tryPlay, { passive: true });
    window.addEventListener("pointermove", tryPlay, { passive: true });
    return () => {
      io.disconnect();
      window.removeEventListener("scroll", tryPlay);
      window.removeEventListener("pointermove", tryPlay);
    };
  }, []);

  const current = CHAPTERS.reduce((acc, c, i) => (time >= c.at ? i : acc), 0);

  return (
    <section className="mkVideo">
      <div className="mkVideoCopy">
        <span className="mkEyebrow">One incident, start to finish</span>
        <h2>Watch it run</h2>
        {onExpand && (
          <button className="mkBtn chip" style={{ marginTop: 6 }} onClick={onExpand}>
            <span className="mkPlayIcon">▶</span> Open full screen
          </button>
        )}
        <p className="mkMuted">
          From the first alert to the customer update, in the time it takes to
          read this sentence twice.
        </p>
        <ol className="mkChapters">
          {CHAPTERS.map((c, i) => (
            <li key={c.label}>
              <button
                className={i === current ? "on" : undefined}
                onClick={() => {
                  const v = video.current;
                  if (!v) return;
                  v.currentTime = c.at;
                  v.play().catch(() => undefined);
                }}
              >
                <span className="mkChapterTime">{c.at.toFixed(1)}s</span>
                {c.label}
              </button>
            </li>
          ))}
        </ol>
      </div>

      <div className="mkVideoFrame">
        <video
          ref={video}
          poster="/media/restora-demo-poster.jpg"
          autoPlay
          muted
          loop
          playsInline
          preload="metadata"
          onTimeUpdate={e => setTime(e.currentTarget.currentTime)}
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
          onClick={e => (e.currentTarget.paused ? e.currentTarget.play() : e.currentTarget.pause())}
        >
          <source src="/media/restora-demo.webm" type="video/webm" />
          <source src="/media/restora-demo.mp4" type="video/mp4" />
        </video>
        {!playing && <span className="mkPlay mkVideoPlay">▶ Play</span>}
        <div className="mkVideoBar" aria-hidden="true">
          <i style={{ width: `${Math.min(100, (time / 12) * 100)}%` }} />
        </div>
      </div>
    </section>
  );
}


/** A silent, looping product clip with its poster as the fallback frame. */
export function LoopVideo({ src, className = "", label }: { src: string; className?: string; label: string }) {
  const ref = useRef<HTMLVideoElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.muted = true;
    el.defaultMuted = true;
    const io = new IntersectionObserver(
      ([e]) => {
        if (e.isIntersecting) el.play().catch(() => undefined);
        else el.pause();
      },
      { threshold: 0.2 }
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return (
    <div className={`mkLoop ${className}`}>
      <video ref={ref} poster={`/media/${src}-poster.jpg`} autoPlay muted loop playsInline preload="auto" aria-label={label}>
        <source src={`/media/${src}.webm`} type="video/webm" />
        <source src={`/media/${src}.mp4`} type="video/mp4" />
      </video>
      <span className="mkLoopTag">
        <i /> {label}
      </span>
    </div>
  );
}

/** The full demo with controls, in a lightbox. Escape or the scrim closes it. */
export function DemoModal({ onClose }: { onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [onClose]);
  return (
    <div className="mkModalScrim" onClick={onClose} role="dialog" aria-modal="true" aria-label="Product demo">
      <div className="mkModal" onClick={e => e.stopPropagation()}>
        <button className="mkModalClose" onClick={onClose} aria-label="Close">
          ✕
        </button>
        <video controls autoPlay playsInline poster="/media/restora-demo-poster.jpg">
          <source src="/media/restora-demo.webm" type="video/webm" />
          <source src="/media/restora-demo.mp4" type="video/mp4" />
        </video>
        <p className="mkModalCaption">
          One incident, start to finish: alert, declaration, agent hypothesis, rollback, monitoring, customer update.
        </p>
      </div>
    </div>
  );
}
