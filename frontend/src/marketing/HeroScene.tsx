import { useEffect, useRef } from "react";
import * as THREE from "three";

/**
 * A slowly rotating graph of nodes and edges behind the hero: services and
 * incidents as points, dependencies as lines. Green for healthy, a few orange
 * points for the ones currently on fire. Follows the pointer a little, and
 * stays still for anyone who asked their OS for reduced motion.
 */
export function HeroScene() {
  const mount = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = mount.current;
    if (!el) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
    camera.position.set(0, 0, 9);

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0x000000, 0);
    el.appendChild(renderer.domElement);

    // Nodes on a squashed sphere so it reads as a globe of systems.
    const COUNT = 220;
    const positions = new Float32Array(COUNT * 3);
    const colors = new Float32Array(COUNT * 3);
    const green = new THREE.Color("#1f8a4c");
    const orange = new THREE.Color("#f25533");
    const pts: THREE.Vector3[] = [];
    for (let i = 0; i < COUNT; i++) {
      const phi = Math.acos(1 - 2 * (i + 0.5) / COUNT);
      const theta = Math.PI * (1 + Math.sqrt(5)) * i;
      const r = 3.2 + (Math.sin(i * 12.9898) * 0.5 + 0.5) * 0.35;
      const v = new THREE.Vector3(
        r * Math.cos(theta) * Math.sin(phi),
        r * Math.sin(theta) * Math.sin(phi) * 0.72,
        r * Math.cos(phi)
      );
      pts.push(v);
      positions.set([v.x, v.y, v.z], i * 3);
      const c = i % 23 === 0 ? orange : green;
      colors.set([c.r, c.g, c.b], i * 3);
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    const points = new THREE.Points(
      geo,
      new THREE.PointsMaterial({ size: 0.07, vertexColors: true, transparent: true, opacity: 0.9 })
    );

    // Edges between near neighbours.
    const edge: number[] = [];
    for (let i = 0; i < COUNT; i++) {
      for (let j = i + 1; j < COUNT; j++) {
        if (pts[i].distanceTo(pts[j]) < 0.9) edge.push(pts[i].x, pts[i].y, pts[i].z, pts[j].x, pts[j].y, pts[j].z);
      }
    }
    const lineGeo = new THREE.BufferGeometry();
    lineGeo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(edge), 3));
    const lines = new THREE.LineSegments(
      lineGeo,
      new THREE.LineBasicMaterial({ color: 0x1f8a4c, transparent: true, opacity: 0.18 })
    );

    const group = new THREE.Group();
    group.add(lines, points);
    group.rotation.x = 0.35;
    scene.add(group);

    // A soft orange pulse on the "incident" nodes.
    const pulseGeo = new THREE.SphereGeometry(0.16, 12, 12);
    const pulseMat = new THREE.MeshBasicMaterial({ color: 0xf25533, transparent: true, opacity: 0.35 });
    const pulses: THREE.Mesh[] = [];
    for (let i = 0; i < COUNT; i += 23) {
      const m = new THREE.Mesh(pulseGeo, pulseMat);
      m.position.copy(pts[i]);
      group.add(m);
      pulses.push(m);
    }

    let target = { x: 0, y: 0 };
    const onMove = (e: PointerEvent) => {
      const r = el.getBoundingClientRect();
      target = { x: (e.clientX - r.left) / r.width - 0.5, y: (e.clientY - r.top) / r.height - 0.5 };
    };
    window.addEventListener("pointermove", onMove, { passive: true });

    const resize = () => {
      const { width, height } = el.getBoundingClientRect();
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(el);

    let raf = 0;
    let t = 0;
    const tick = () => {
      t += reduced ? 0 : 0.004;
      group.rotation.y = t + target.x * 0.4;
      group.rotation.x = 0.35 + target.y * 0.25;
      const s = 1 + Math.sin(t * 6) * 0.35;
      for (const p of pulses) p.scale.setScalar(s);
      renderer.render(scene, camera);
      raf = requestAnimationFrame(tick);
    };
    tick();

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      window.removeEventListener("pointermove", onMove);
      renderer.dispose();
      geo.dispose();
      lineGeo.dispose();
      pulseGeo.dispose();
      el.removeChild(renderer.domElement);
    };
  }, []);

  return <div ref={mount} className="mkScene" aria-hidden="true" />;
}
