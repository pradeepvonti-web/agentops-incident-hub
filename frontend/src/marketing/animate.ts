import { useEffect, type RefObject } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

gsap.registerPlugin(ScrollTrigger);

/**
 * Every animation on the marketing page, in one place, scoped to `root` so it
 * is torn down cleanly when the page unmounts. Elements opt in with data
 * attributes rather than classes, so the markup says what it does:
 *
 *   data-reveal            fade + rise when scrolled into view
 *   data-reveal="stagger"  same, but children arrive one after another
 *   data-parallax="0.2"    drifts at a fraction of scroll speed
 *   data-count="1200"      counts up from 0 to the number
 *   data-marquee           scrolls its content sideways forever
 */
export function useMarketingAnimations(root: RefObject<HTMLElement | null>) {
  useEffect(() => {
    const el = root.current;
    if (!el) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const ctx = gsap.context(() => {
      if (reduced) {
        gsap.set("[data-reveal], [data-reveal] > *, [data-hero]", { opacity: 1, y: 0 });
        return;
      }

      // Hero: the headline arrives word by word, then everything under it.
      const words = el.querySelectorAll<HTMLElement>("[data-hero-word]");
      gsap.set(words, { yPercent: 110, opacity: 0 });
      gsap.set("[data-hero]", { y: 24, opacity: 0 });
      gsap
        .timeline({ defaults: { ease: "power3.out" } })
        .to(words, { yPercent: 0, opacity: 1, duration: 0.9, stagger: 0.06 }, 0.1)
        .to("[data-hero]", { y: 0, opacity: 1, duration: 0.8, stagger: 0.12 }, 0.5);

      // The product stage rises in and then drifts slower than the page.
      const stage = el.querySelector<HTMLElement>("[data-stage]");
      if (stage) {
        gsap.from(stage, { y: 80, opacity: 0, duration: 1.1, ease: "power3.out", delay: 0.7 });
        gsap.to(stage, {
          yPercent: -6,
          ease: "none",
          scrollTrigger: { trigger: stage, start: "top bottom", end: "bottom top", scrub: true }
        });
      }

      // Scroll reveals.
      el.querySelectorAll<HTMLElement>("[data-reveal]").forEach(node => {
        const stagger = node.dataset.reveal === "stagger";
        const targets = stagger ? Array.from(node.children) : [node];
        gsap.fromTo(
          targets,
          { y: 28, opacity: 0 },
          {
            y: 0,
            opacity: 1,
            duration: 0.7,
            ease: "power3.out",
            stagger: stagger ? 0.08 : 0,
            immediateRender: true,
            scrollTrigger: { trigger: node, start: "top 92%", once: true }
          }
        );
      });

      // Parallax layers.
      el.querySelectorAll<HTMLElement>("[data-parallax]").forEach(node => {
        const amount = Number(node.dataset.parallax || 0.2);
        gsap.to(node, {
          yPercent: -amount * 100,
          ease: "none",
          scrollTrigger: { trigger: node, start: "top bottom", end: "bottom top", scrub: true }
        });
      });

      // Counters.
      el.querySelectorAll<HTMLElement>("[data-count]").forEach(node => {
        const end = Number(node.dataset.count || 0);
        const suffix = node.dataset.suffix ?? "";
        const obj = { v: 0 };
        gsap.to(obj, {
          v: end,
          duration: 1.6,
          ease: "power2.out",
          scrollTrigger: { trigger: node, start: "top 85%", once: true },
          onUpdate: () => {
            node.textContent = Math.round(obj.v).toLocaleString() + suffix;
          }
        });
      });

      // Marquee: the track holds two copies, so half a width is a full loop.
      el.querySelectorAll<HTMLElement>("[data-marquee]").forEach(track => {
        gsap.to(track, { xPercent: -50, ease: "none", duration: 38, repeat: -1 });
      });

      // The Problem/Solution toggle and the pillar visuals get a small lift.
      el.querySelectorAll<HTMLElement>("[data-float]").forEach(node => {
        gsap.to(node, { y: -8, duration: 2.4, ease: "sine.inOut", yoyo: true, repeat: -1 });
      });
    }, el);

    // Layout settles late (web fonts, the video poster, the 3D canvas), so
    // trigger positions are recomputed once everything has loaded.
    const refresh = () => ScrollTrigger.refresh();
    window.addEventListener("load", refresh);
    document.fonts?.ready.then(refresh);
    const settle = window.setTimeout(refresh, 1200);

    // Failsafe: nothing may stay hidden because a trigger never fired or the
    // ticker was throttled in a background tab while the page loaded.
    const failsafe = window.setTimeout(() => {
      gsap.to(el.querySelectorAll("[data-hero], [data-hero-word], [data-stage], [data-reveal], [data-reveal] > *"),
        { opacity: 1, y: 0, yPercent: 0, duration: 0.6, overwrite: "auto" });
    }, 3000);

    return () => {
      window.removeEventListener("load", refresh);
      window.clearTimeout(settle);
      window.clearTimeout(failsafe);
      ctx.revert();
    };
  }, [root]);
}

/** Re-run reveals for content that changed after mount (e.g. a tab switch). */
export function refreshScroll() {
  ScrollTrigger.refresh();
}
