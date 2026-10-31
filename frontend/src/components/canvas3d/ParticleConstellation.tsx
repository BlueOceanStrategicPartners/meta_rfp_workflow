import { useEffect, useRef } from "react";

const PARTICLE_COUNT = 58;
const CONNECT_FRAC = 0.22;
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

    const particles: Particle[] = [];
    const linkAlphas = new Float32Array(PARTICLE_COUNT * PARTICLE_COUNT);
    const linkDesired = new Float32Array(PARTICLE_COUNT * PARTICLE_COUNT);
    const linkFlipAt = new Float32Array(PARTICLE_COUNT * PARTICLE_COUNT);

    let polygon: PolygonPulse | null = null;
    let nextPolygonAt = 0;

    const spawnParticles = () => {
      particles.length = 0;
      const padX = width * 0.08;
      const padY = height * 0.1;
      for (let i = 0; i < PARTICLE_COUNT; i++) {
        particles.push({
          x: padX + Math.random() * (width - padX * 2),
          y: padY + Math.random() * (height - padY * 2),
          z: Math.random(),
          vx: (Math.random() - 0.5) * 28,
          vy: (Math.random() - 0.5) * 22,
        });
      }
      for (let i = 0; i < PARTICLE_COUNT; i++) {
        for (let j = i + 1; j < PARTICLE_COUNT; j++) {
          const idx = pairIndex(i, j, PARTICLE_COUNT);
          linkDesired[idx] = 0.55 + Math.random() * 0.45;
          linkFlipAt[idx] = Math.random() * 1.5;
          linkAlphas[idx] = 0;
        }
      }
    };

    const resize = () => {
      const parent = canvas.parentElement;
      if (!parent) return;
      width = parent.clientWidth;
      height = parent.clientHeight;
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      connectDist = Math.min(width, height) * CONNECT_FRAC;
      if (particles.length === 0) spawnParticles();
    };

    const spawnPolygonPulse = (timeSec: number) => {
      const anchor = Math.floor(Math.random() * PARTICLE_COUNT);
      const ax = particles[anchor].x;
      const ay = particles[anchor].y;
      const neighbors = particles
        .map((p, idx) => ({
          idx,
          dist: (p.x - ax) ** 2 + (p.y - ay) ** 2,
        }))
        .filter(({ idx, dist }) => idx !== anchor && dist < connectDist * connectDist * 1.4)
        .sort((a, b) => a.dist - b.dist)
        .slice(0, 3 + Math.floor(Math.random() * 2))
        .map(({ idx }) => idx);

      if (neighbors.length < 2) {
        nextPolygonAt = timeSec + 0.35;
        return;
      }
      polygon = {
        indices: [anchor, ...neighbors],
        startTime: timeSec,
        duration: 2.2 + Math.random() * 1.3,
      };
      nextPolygonAt = timeSec + 1.8 + Math.random() * 2;
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

      const padX = width * 0.06;
      const padY = height * 0.08;
      for (const p of particles) {
        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.z += (Math.random() - 0.5) * 0.015;
        p.z = Math.max(0, Math.min(1, p.z));

        if (p.x < padX || p.x > width - padX) p.vx *= -1;
        if (p.y < padY || p.y > height - padY) p.vy *= -1;
        p.x = Math.max(padX, Math.min(width - padX, p.x));
        p.y = Math.max(padY, Math.min(height - padY, p.y));
      }

      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.fillStyle = "#020617";
      ctx.fillRect(0, 0, width, height);

      const lerpSpeed = 1 - Math.pow(0.0008, dt);
      ctx.lineCap = "round";

      for (let i = 0; i < PARTICLE_COUNT; i++) {
        for (let j = i + 1; j < PARTICLE_COUNT; j++) {
          const pi = particles[i];
          const pj = particles[j];
          const dx = pi.x - pj.x;
          const dy = pi.y - pj.y;
          const dist = Math.hypot(dx, dy);
          const idx = pairIndex(i, j, PARTICLE_COUNT);
          let targetAlpha = 0;

          if (dist < connectDist) {
            if (timeSec >= linkFlipAt[idx]) {
              const roll = Math.random();
              if (linkDesired[idx] < 0.05) {
                linkDesired[idx] = roll < 0.65 ? 0.5 + Math.random() * 0.5 : 0;
              } else {
                linkDesired[idx] = roll < 0.42 ? 0 : 0.45 + Math.random() * 0.55;
              }
              linkFlipAt[idx] = timeSec + 0.45 + Math.random() * 2;
            }
            const proximity = 1 - dist / connectDist;
            targetAlpha = proximity * proximity * linkDesired[idx];
          } else {
            linkDesired[idx] = 0;
            linkFlipAt[idx] = timeSec + 0.2 + Math.random() * 0.9;
          }

          if (pulseStrength > 0 && pulseSet.has(i) && pulseSet.has(j)) {
            targetAlpha = Math.max(targetAlpha, pulseStrength * 0.95);
          }

          linkAlphas[idx] += (targetAlpha - linkAlphas[idx]) * lerpSpeed;
          const alpha = linkAlphas[idx];
          if (alpha < 0.05) continue;

          const depth = 0.45 + ((pi.z + pj.z) * 0.5) * 0.55;
          const lineAlpha = Math.min(0.85, alpha * depth * 0.95);

          ctx.beginPath();
          ctx.strokeStyle = `rgba(${LINK_RGBA}, ${lineAlpha})`;
          ctx.lineWidth = 1.15 + depth * 0.65;
          ctx.moveTo(pi.x, pi.y);
          ctx.lineTo(pj.x, pj.y);
          ctx.stroke();
        }
      }

      for (const p of particles) {
        const depth = 0.18 + p.z * 0.82;
        const radius = 0.85 + depth * 1.15;
        ctx.beginPath();
        ctx.fillStyle = `rgba(224, 242, 254, ${depth})`;
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
      className="pointer-events-none absolute inset-0 -z-10 block h-full w-full"
      aria-hidden
    />
  );
}
