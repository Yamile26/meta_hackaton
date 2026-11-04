import { useEffect, useRef } from "react";

/**
 * Subtle animated backdrop: slowly drifting light-green contour lines (value
 * noise + marching squares) and a faint radar sweep. Pure 2D canvas, no libraries.
 * - fixed, behind everything, pointer-events: none, opacity ≤ 12 % (clamped)
 * - ≤ 30 fps; contours are re-traced only ~6×/s into an offscreen canvas
 * - devicePixelRatio capped at 1.5; paused while the tab is hidden
 * - prefers-reduced-motion: draws a single static frame
 */

const MAX_OPACITY = 0.12;
const FRAME_MS = 1000 / 30;
const CONTOUR_MS = 160;
const CELL = 22; // grid size in CSS px for marching squares
const LEVELS = [-0.55, -0.4, -0.25, -0.1, 0.05, 0.2, 0.35, 0.5];
const LINE = "#3FA66B"; // leaf
const LINE_STRONG = "#1F7A4D"; // brand green, every 4th level
const SWEEP_PERIOD_S = 14;

function hash(x: number, y: number): number {
  let h = (x * 374761393 + y * 668265263) | 0;
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  return ((h ^ (h >>> 16)) & 0xffff) / 0x7fff - 1; // [-1, 1]
}

function noise(x: number, y: number): number {
  const ix = Math.floor(x);
  const iy = Math.floor(y);
  const fx = x - ix;
  const fy = y - iy;
  const sx = fx * fx * (3 - 2 * fx);
  const sy = fy * fy * (3 - 2 * fy);
  const a = hash(ix, iy);
  const b = hash(ix + 1, iy);
  const c = hash(ix, iy + 1);
  const d = hash(ix + 1, iy + 1);
  return a + (b - a) * sx + (c - a) * sy + (a - b - c + d) * sx * sy;
}

function field(x: number, y: number, t: number): number {
  return 0.7 * noise(x * 0.0042 + t * 0.012, y * 0.0042 - t * 0.008) + 0.3 * noise(x * 0.011 - t * 0.01, y * 0.011 + t * 0.014);
}

/** Traces iso-lines of the noise field into ctx (CSS px coordinates). */
function drawContours(ctx: CanvasRenderingContext2D, w: number, h: number, t: number) {
  const cols = Math.ceil(w / CELL) + 1;
  const rows = Math.ceil(h / CELL) + 1;
  const v = new Float32Array(cols * rows);
  for (let j = 0; j < rows; j++) for (let i = 0; i < cols; i++) v[j * cols + i] = field(i * CELL, j * CELL, t);

  ctx.clearRect(0, 0, w, h);
  ctx.lineWidth = 1;
  LEVELS.forEach((level, li) => {
    ctx.beginPath();
    for (let j = 0; j < rows - 1; j++) {
      for (let i = 0; i < cols - 1; i++) {
        const a = v[j * cols + i]; // top-left
        const b = v[j * cols + i + 1]; // top-right
        const c = v[(j + 1) * cols + i + 1]; // bottom-right
        const d = v[(j + 1) * cols + i]; // bottom-left
        const idx = (a > level ? 8 : 0) | (b > level ? 4 : 0) | (c > level ? 2 : 0) | (d > level ? 1 : 0);
        if (idx === 0 || idx === 15) continue;
        const x = i * CELL;
        const y = j * CELL;
        const lerp = (p: number, q: number) => (level - p) / (q - p);
        const top: [number, number] = [x + CELL * lerp(a, b), y];
        const right: [number, number] = [x + CELL, y + CELL * lerp(b, c)];
        const bottom: [number, number] = [x + CELL * lerp(d, c), y + CELL];
        const left: [number, number] = [x, y + CELL * lerp(a, d)];
        const seg = (p: [number, number], q: [number, number]) => {
          ctx.moveTo(p[0], p[1]);
          ctx.lineTo(q[0], q[1]);
        };
        switch (idx) {
          case 1: case 14: seg(left, bottom); break;
          case 2: case 13: seg(bottom, right); break;
          case 3: case 12: seg(left, right); break;
          case 4: case 11: seg(top, right); break;
          case 6: case 9: seg(top, bottom); break;
          case 7: case 8: seg(left, top); break;
          case 5: seg(left, top); seg(bottom, right); break;
          case 10: seg(top, right); seg(left, bottom); break;
        }
      }
    }
    ctx.strokeStyle = li % 4 === 3 ? LINE_STRONG : LINE;
    ctx.globalAlpha = li % 4 === 3 ? 0.8 : 0.6;
    ctx.stroke();
  });
  ctx.globalAlpha = 1;
}

function drawRadar(ctx: CanvasRenderingContext2D, w: number, h: number, angle: number, withSweep: boolean) {
  const cx = w * 0.5;
  const cy = h * 0.55;
  const r = Math.hypot(w, h) * 0.6;

  // Static range rings.
  ctx.strokeStyle = LINE;
  ctx.globalAlpha = 0.3;
  ctx.lineWidth = 1;
  for (let rr = 160; rr < r; rr += 160) {
    ctx.beginPath();
    ctx.arc(cx, cy, rr, 0, Math.PI * 2);
    ctx.stroke();
  }
  ctx.globalAlpha = 1;
  if (!withSweep || typeof ctx.createConicGradient !== "function") return;

  // Trailing wedge (leaf green) with a slightly stronger leading edge.
  const trail = 0.9;
  const g = ctx.createConicGradient(angle - trail, cx, cy);
  const f = trail / (Math.PI * 2);
  g.addColorStop(0, "rgba(63,166,107,0)");
  g.addColorStop(f, "rgba(63,166,107,0.5)");
  g.addColorStop(Math.min(1, f + 0.001), "rgba(63,166,107,0)");
  g.addColorStop(1, "rgba(63,166,107,0)");
  ctx.fillStyle = g;
  ctx.beginPath();
  ctx.moveTo(cx, cy);
  ctx.arc(cx, cy, r, angle - trail, angle);
  ctx.closePath();
  ctx.fill();

  ctx.strokeStyle = LINE_STRONG;
  ctx.globalAlpha = 0.6;
  ctx.beginPath();
  ctx.moveTo(cx, cy);
  ctx.lineTo(cx + Math.cos(angle) * r, cy + Math.sin(angle) * r);
  ctx.stroke();
  ctx.globalAlpha = 1;
}

/** opacity: 0.12 on the landing page, lower inside the app. Clamped to ≤ 12 %. */
export function BackgroundCanvas({ opacity = MAX_OPACITY }: { opacity?: number }) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    const off = document.createElement("canvas");
    const offCtx = off.getContext("2d");
    if (!offCtx) return;

    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    let w = 0;
    let h = 0;
    let dpr = 1;
    let raf = 0;
    let lastFrame = 0;
    let lastContour = -Infinity;
    const t0 = performance.now();

    const resize = () => {
      dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      w = window.innerWidth;
      h = window.innerHeight;
      for (const c of [canvas, off]) {
        c.width = Math.round(w * dpr);
        c.height = Math.round(h * dpr);
      }
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      offCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
      lastContour = -Infinity;
    };

    const render = (now: number, animated: boolean) => {
      const t = animated ? (now - t0) / 1000 : 0;
      if (now - lastContour >= CONTOUR_MS) {
        drawContours(offCtx, w, h, t);
        lastContour = now;
      }
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(off, 0, 0);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const angle = animated ? ((t / SWEEP_PERIOD_S) * Math.PI * 2) % (Math.PI * 2) : -Math.PI / 4;
      drawRadar(ctx, w, h, angle, animated);
    };

    const loop = (now: number) => {
      raf = requestAnimationFrame(loop);
      if (now - lastFrame < FRAME_MS) return;
      lastFrame = now;
      render(now, true);
    };

    const start = () => {
      cancelAnimationFrame(raf);
      raf = 0;
      if (motion.matches) {
        render(performance.now(), false); // static frame
      } else if (!document.hidden) {
        raf = requestAnimationFrame(loop);
      }
    };

    const onResize = () => {
      resize();
      start();
    };
    const onVisibility = () => (document.hidden ? cancelAnimationFrame(raf) : start());

    resize();
    start();
    window.addEventListener("resize", onResize);
    document.addEventListener("visibilitychange", onVisibility);
    motion.addEventListener("change", start);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", onResize);
      document.removeEventListener("visibilitychange", onVisibility);
      motion.removeEventListener("change", start);
    };
  }, []);

  return (
    <canvas
      ref={ref}
      aria-hidden
      className="pointer-events-none fixed inset-0 z-0"
      style={{ opacity: Math.min(opacity, MAX_OPACITY), transition: "opacity 400ms ease" }}
    />
  );
}
