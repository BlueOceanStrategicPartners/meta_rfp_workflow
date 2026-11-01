import { useEffect, useRef } from "react";

const PARTICLE_COUNT = 52;
/** Shorter links — less mesh clutter; corners still connect locally */
const CONNECT_FRAC = 0.16;
const LINK_RGBA = "186, 230, 253";

function easeInOutCubic(t: number) {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

function pairIndex(i: number, j: number, count: number) {
  if (i > j) [i, j] = [j, i];
  return i * count + j;
}

type Particle = {
  x: number;
  y: number;
  z: number;
  vx: number;
  vy: number;
};

type PolygonPulse = {
  indices: number[];
  startTime: number;
  duration: number;
};

type Exclusion = { cx: number; cy: number; rx: number; ry: number };

function exclusionForSize(width: number, height: number): Exclusion {
  const min = Math.min(width, height);
  return {
    cx: width / 2,
    cy: height * 0.46,
    rx: min * 0.34,
    ry: min * 0.38,
  };
}

function inExclusion(x: number, y: number, ex: Exclusion): boolean {
  const nx = (x - ex.cx) / ex.rx;
  const ny = (y - ex.cy) / ex.ry;
  return nx * nx + ny * ny < 1;
}

/** Bias spawn toward corners and edges; keep the voice orb corridor clear */
function randomPositionOutsideCenter(width: number, height: number, ex: Exclusion): { x: number; y: number } {
  const padX = width * 0.035;
  const padY = height * 0.05;

  const tryPoint = (x: number, y: number) => {
    if (x < padX || x > width - padX || y < padY || y > height - padY) return null;
    if (inExclusion(x, y, ex)) return null;
    return { x, y };
  };

  for (let attempt = 0; attempt < 60; attempt++) {
    if (Math.random() < 0.78) {
      const corner = Math.floor(Math.random() * 4);
      const left = corner === 0 || corner === 2;
      const top = corner === 0 || corner === 1;
      const x0 = left ? padX : width * 0.52;
      const x1 = left ? width * 0.48 : width - padX;
      const y0 = top ? padY : height * 0.52;
      const y1 = top ? height * 0.48 : height - padY;
      const p = tryPoint(x0 + Math.random() * (x1 - x0), y0 + Math.random() * (y1 - y0));
      if (p) return p;
    } else {
      const band = Math.floor(Math.random() * 4);
      let x = padX + Math.random() * (width - padX * 2);
      let y = padY + Math.random() * (height - padY * 2);
      if (band === 0) y = padY + Math.random() * (height * 0.14);
      if (band === 1) y = height - padY - Math.random() * (height * 0.14);
      if (band === 2) x = padX + Math.random() * (width * 0.12);
      if (band === 3) x = width - padX - Math.random() * (width * 0.12);
      const p = tryPoint(x, y);
      if (p) return p;
    }
  }

  const fallback = [
    { x: padX + 24, y: padY + 24 },
    { x: width - padX - 24, y: padY + 24 },
    { x: padX + 24, y: height - padY - 24 },
    { x: width - padX - 24, y: height - padY - 24 },
  ];
  return fallback[Math.floor(Math.random() * fallback.length)];
}

function pushOutOfExclusion(p: Particle, ex: Exclusion) {
  const dx = p.x - ex.cx;
  const dy = p.y - ex.cy;
  const nx = dx / ex.rx;
  const ny = dy / ex.ry;
  const d2 = nx * nx + ny * ny;
  if (d2 >= 1) return;
  const scale = 1.04 / Math.sqrt(d2 || 1e-6);
  p.x = ex.cx + dx * scale;
  p.y = ex.cy + dy * scale;
  const len = Math.hypot(dx, dy) || 1;
  p.vx += (dx / len) * 22;
  p.vy += (dy / len) * 22;
}

function segmentMidpointInExclusion(
  x1: number,
  y1: number,
  x2: number,
  y2: number,
  ex: Exclusion,
): boolean {
  const mx = (x1 + x2) * 0.5;
  const my = (y1 + y2) * 0.5;
  return inExclusion(mx, my, ex);
}

export default function ParticleConstellation() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let width = 0;
    let height = 0;
    let dpr = 1;
    let connectDist = 120;
    let raf = 0;
    let startTime = performance.now();
    let ex: Exclusion = { cx: 0, cy: 0, rx: 1, ry: 1 };

    const particles: Particle[] = [];
    const linkAlphas = new Float32Array(PARTICLE_COUNT * PARTICLE_COUNT);
    const linkDesired = new Float32Array(PARTICLE_COUNT * PARTICLE_COUNT);
    const linkFlipAt = new Float32Array(PARTICLE_COUNT * PARTICLE_COUNT);

    let polygon: PolygonPulse | null = null;
    let nextPolygonAt = 0;

    const spawnParticles = () => {
      particles.length = 0;
      ex = exclusionForSize(width, height);
      for (let i = 0; i < PARTICLE_COUNT; i++) {
        const { x, y } = randomPositionOutsideCenter(width, height, ex);
        particles.push({
          x,
          y,
          z: Math.random(),
          vx: (Math.random() - 0.5) * 22,
          vy: (Math.random() - 0.5) * 18,
        });
      }
      for (let i = 0; i < PARTICLE_COUNT; i++) {
        for (let j = i + 1; j < PARTICLE_COUNT; j++) {
          const idx = pairIndex(i, j, PARTICLE_COUNT);
          linkDesired[idx] = 0.5 + Math.random() * 0.45;
          linkFlipAt[idx] = Math.random() * 1.5;
          linkAlphas[idx] = 0;
        }
      }
    };

    const resize = () => {
      const parent = canvas.parentElement;
      if (!parent) return;
      width = parent.clientWidth || window.innerWidth;
      height = parent.clientHeight || Math.max(window.innerHeight - 120, 400);
      if (width < 1 || height < 1) return;
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      connectDist = Math.min(width, height) * CONNECT_FRAC;
      ex = exclusionForSize(width, height);
      if (particles.length === 0) spawnParticles();
    };

    const spawnPolygonPulse = (timeSec: number) => {
      const outside = particles
        .map((p, idx) => ({ idx, p }))
        .filter(({ p }) => !inExclusion(p.x, p.y, ex));
      if (outside.length < 3) {
        nextPolygonAt = timeSec + 0.5;
        return;
      }
      const anchorEntry = outside[Math.floor(Math.random() * outside.length)];
      const ax = anchorEntry.p.x;
      const ay = anchorEntry.p.y;
      const neighbors = outside
        .filter(({ idx }) => idx !== anchorEntry.idx)
        .map(({ idx, p }) => ({
          idx,
          dist: (p.x - ax) ** 2 + (p.y - ay) ** 2,
        }))
        .filter(({ dist }) => dist < connectDist * connectDist * 1.25)
        .sort((a, b) => a.dist - b.dist)
        .slice(0, 2 + Math.floor(Math.random() * 2))
        .map(({ idx }) => idx);

      if (neighbors.length < 2) {
        nextPolygonAt = timeSec + 0.45;
        return;
      }
      polygon = {
        indices: [anchorEntry.idx, ...neighbors],
        startTime: timeSec,
        duration: 2 + Math.random() * 1.1,
      };
      nextPolygonAt = timeSec + 2.2 + Math.random() * 2.5;
    };

    const frame = (now: number) => {
      const timeSec = (now - startTime) / 1000;
      const dt = Math.min(0.05, 1 / 60);

      if (nextPolygonAt === 0 || timeSec >= nextPolygonAt) {
        spawnPolygonPulse(timeSec);
      }

      let pulseStrength = 0;
      const pulseSet = new Set<number>();
      if (polygon) {
        const phase = (timeSec - polygon.startTime) / polygon.duration;
        if (phase >= 0 && phase <= 1) {
          pulseStrength = easeInOutCubic(Math.sin(phase * Math.PI));
          polygon.indices.forEach((idx) => pulseSet.add(idx));
        } else if (phase > 1) {
          polygon = null;
        }
      }

      const padX = width * 0.03;
      const padY = height * 0.04;
      for (const p of particles) {
        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.z += (Math.random() - 0.5) * 0.012;
        p.z = Math.max(0, Math.min(1, p.z));

        if (p.x < padX || p.x > width - padX) p.vx *= -1;
        if (p.y < padY || p.y > height - padY) p.vy *= -1;
        p.x = Math.max(padX, Math.min(width - padX, p.x));
        p.y = Math.max(padY, Math.min(height - padY, p.y));
        pushOutOfExclusion(p, ex);
      }

      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, width, height);

      const lerpSpeed = 1 - Math.pow(0.0008, dt);
      ctx.lineCap = "round";

      for (let i = 0; i < PARTICLE_COUNT; i++) {
        for (let j = i + 1; j < PARTICLE_COUNT; j++) {
          const pi = particles[i];
          const pj = particles[j];
          if (
            inExclusion(pi.x, pi.y, ex) ||
            inExclusion(pj.x, pj.y, ex) ||
            segmentMidpointInExclusion(pi.x, pi.y, pj.x, pj.y, ex)
          ) {
            const idx = pairIndex(i, j, PARTICLE_COUNT);
            linkAlphas[idx] += (0 - linkAlphas[idx]) * lerpSpeed;
            continue;
          }

          const dx = pi.x - pj.x;
          const dy = pi.y - pj.y;
          const dist = Math.hypot(dx, dy);
          const idx = pairIndex(i, j, PARTICLE_COUNT);
          let targetAlpha = 0;

          if (dist < connectDist) {
            if (timeSec >= linkFlipAt[idx]) {
              const roll = Math.random();
              if (linkDesired[idx] < 0.05) {
                linkDesired[idx] = roll < 0.65 ? 0.45 + Math.random() * 0.45 : 0;
              } else {
                linkDesired[idx] = roll < 0.42 ? 0 : 0.4 + Math.random() * 0.5;
              }
              linkFlipAt[idx] = timeSec + 0.45 + Math.random() * 2;
            }
            const proximity = 1 - dist / connectDist;
            targetAlpha = proximity * proximity * linkDesired[idx] * 0.85;
          } else {
            linkDesired[idx] = 0;
            linkFlipAt[idx] = timeSec + 0.2 + Math.random() * 0.9;
          }

          if (pulseStrength > 0 && pulseSet.has(i) && pulseSet.has(j)) {
            targetAlpha = Math.max(targetAlpha, pulseStrength * 0.75);
          }

          linkAlphas[idx] += (targetAlpha - linkAlphas[idx]) * lerpSpeed;
          const alpha = linkAlphas[idx];
          if (alpha < 0.05) continue;

          const depth = 0.4 + ((pi.z + pj.z) * 0.5) * 0.5;
          const lineAlpha = Math.min(0.72, alpha * depth * 0.9);

          ctx.beginPath();
          ctx.strokeStyle = `rgba(${LINK_RGBA}, ${lineAlpha})`;
          ctx.lineWidth = 1 + depth * 0.55;
          ctx.moveTo(pi.x, pi.y);
          ctx.lineTo(pj.x, pj.y);
          ctx.stroke();
        }
      }

      for (const p of particles) {
        if (inExclusion(p.x, p.y, ex)) continue;
        const depth = 0.16 + p.z * 0.78;
        const radius = 0.75 + depth * 1.05;
        ctx.beginPath();
        ctx.fillStyle = `rgba(224, 242, 254, ${depth * 0.92})`;
        ctx.arc(p.x, p.y, radius, 0, Math.PI * 2);
        ctx.fill();
      }

      raf = requestAnimationFrame(frame);
    };

    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas.parentElement ?? canvas);
    raf = requestAnimationFrame(frame);

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="pointer-events-none absolute inset-0 z-0 block h-full w-full"
      aria-hidden
    />
  );
}
