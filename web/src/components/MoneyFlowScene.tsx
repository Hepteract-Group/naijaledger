import { useEffect, useId, useRef } from "react";
import { motion, useReducedMotion, useScroll, useMotionValueEvent } from "motion/react";

type Particle = {
  x: number;
  y: number;
  vx: number;
  vy: number;
  r: number;
  gold: boolean;
};

/** Particle field that reacts to scroll. Pair with CivicMapSvg for the landform. */
function ParticleField() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const hostRef = useRef<HTMLDivElement | null>(null);
  const progressRef = useRef(0);
  const reduce = useReducedMotion();
  const { scrollYProgress } = useScroll({
    target: hostRef,
    offset: ["start start", "end start"],
  });

  useMotionValueEvent(scrollYProgress, "change", (v) => {
    progressRef.current = v;
  });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) {
      return;
    }
    let ctx: CanvasRenderingContext2D | null = null;
    try {
      ctx = canvas.getContext("2d");
    } catch {
      return;
    }
    if (!ctx) {
      return;
    }

    let raf = 0;
    let particles: Particle[] = [];
    let width = 0;
    let height = 0;

    const spawn = (w: number, h: number): Particle => ({
      x: Math.random() * w,
      y: Math.random() * h,
      vx: (Math.random() - 0.2) * 0.55,
      vy: (Math.random() - 0.5) * 0.32,
      r: 1 + Math.random() * 2.8,
      gold: Math.random() > 0.55,
    });

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = canvas.clientWidth;
      height = canvas.clientHeight;
      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      particles = Array.from({ length: reduce ? 20 : 140 }, () => spawn(width, height));
    };

    const tick = () => {
      const t = Math.min(1, Math.max(0, progressRef.current));
      ctx.clearRect(0, 0, width, height);

      const g = ctx.createRadialGradient(
        width * 0.7,
        height * 0.35,
        20,
        width * 0.55,
        height * 0.5,
        Math.max(width, height) * 0.8,
      );
      g.addColorStop(0, `hsla(158, 70%, 45%, ${0.22 + t * 0.18})`);
      g.addColorStop(0.55, "hsla(210, 40%, 12%, 0.12)");
      g.addColorStop(1, "hsla(150, 20%, 5%, 0)");
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, width, height);

      const speed = reduce ? 0 : 0.9 + t * 2.2;
      for (const p of particles) {
        if (!reduce) {
          p.x += p.vx * speed;
          p.y += p.vy * speed;
          if (p.x < -14) p.x = width + 14;
          if (p.x > width + 14) p.x = -14;
          if (p.y < -14) p.y = height + 14;
          if (p.y > height + 14) p.y = -14;
        }
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = p.gold
          ? `hsla(42, 92%, 62%, ${0.45 + t * 0.4})`
          : `hsla(158, 80%, 58%, ${0.4 + t * 0.45})`;
        ctx.fill();
      }

      if (!reduce) {
        ctx.lineWidth = 0.7;
        for (let i = 0; i < particles.length; i += 1) {
          for (let j = i + 1; j < i + 4 && j < particles.length; j += 1) {
            const a = particles[i];
            const b = particles[j];
            const dx = a.x - b.x;
            const dy = a.y - b.y;
            const d2 = dx * dx + dy * dy;
            if (d2 < 85 * 85) {
              ctx.strokeStyle = `hsla(158, 60%, 65%, ${0.14 * (1 - d2 / (85 * 85))})`;
              ctx.beginPath();
              ctx.moveTo(a.x, a.y);
              ctx.lineTo(b.x, b.y);
              ctx.stroke();
            }
          }
        }
      }

      raf = requestAnimationFrame(tick);
    };

    resize();
    window.addEventListener("resize", resize);
    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
    };
  }, [reduce]);

  return (
    <div ref={hostRef} className="money-flow-host" aria-hidden>
      <canvas ref={canvasRef} className="money-flow" />
    </div>
  );
}

/** Recognisable Nigeria landform with animated money trails (not a decorative circle). */
function CivicMapSvg() {
  const reduce = useReducedMotion();
  const gid = useId().replace(/:/g, "");

  return (
    <svg className="civic-map" viewBox="0 0 520 480" aria-hidden>
      <defs>
        <linearGradient id={`${gid}-fill`} x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.35" />
          <stop offset="100%" stopColor="var(--indigo)" stopOpacity="0.2" />
        </linearGradient>
        <filter id={`${gid}-glow`} x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="4" result="b" />
          <feMerge>
            <feMergeNode in="b" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
      {/* Simplified but recognisable Nigeria outline */}
      <motion.path
        d="M168 72
           C210 48 268 42 318 58
           C360 72 402 98 428 138
           C458 188 468 242 452 298
           C432 368 382 418 318 442
           C258 464 198 452 158 410
           C118 368 98 308 102 248
           C106 188 128 118 168 72 Z"
        fill={`url(#${gid}-fill)`}
        stroke="var(--accent)"
        strokeWidth="2.5"
        filter={`url(#${gid}-glow)`}
        initial={reduce ? false : { pathLength: 0, opacity: 0.4 }}
        animate={reduce ? undefined : { pathLength: 1, opacity: 1 }}
        transition={{ duration: 2.4, ease: [0.22, 1, 0.36, 1] }}
      />
      {[
        "M150 160 C210 140 270 180 330 165 C380 152 420 190 450 210",
        "M140 240 C200 220 260 270 320 250 C380 230 420 280 455 290",
        "M155 320 C220 300 280 350 350 330 C400 318 430 360 450 370",
      ].map((d, i) => (
        <motion.path
          key={d}
          d={d}
          fill="none"
          stroke={i % 2 === 0 ? "var(--gold-bright)" : "var(--accent)"}
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeDasharray="6 11"
          initial={false}
          animate={reduce ? undefined : { strokeDashoffset: [0, -64] }}
          transition={{ duration: 6 + i, repeat: Infinity, ease: "linear" }}
          opacity={0.75}
        />
      ))}
      {(
        [
          [220, 150],
          [300, 180],
          [260, 240],
          [340, 280],
          [200, 300],
          [380, 220],
        ] as const
      ).map(([cx, cy], i) => (
        <g key={`${cx}-${cy}`}>
          <motion.circle
            cx={cx}
            cy={cy}
            r={4}
            fill={i % 2 === 0 ? "var(--gold-bright)" : "var(--accent)"}
            animate={reduce ? undefined : { opacity: [0.5, 1, 0.5], scale: [1, 1.25, 1] }}
            transition={{ duration: 2.2 + i * 0.2, repeat: Infinity, ease: "easeInOut" }}
          />
          <motion.circle
            cx={cx}
            cy={cy}
            r={12}
            fill="none"
            stroke="var(--accent)"
            strokeWidth="1"
            animate={reduce ? undefined : { r: [10, 22], opacity: [0.45, 0] }}
            transition={{ duration: 2.4, repeat: Infinity, ease: "easeOut", delay: i * 0.15 }}
          />
        </g>
      ))}
    </svg>
  );
}

export function MoneyFlowScene() {
  return (
    <div className="money-flow-stage" aria-hidden>
      <ParticleField />
      <div className="civic-map-wrap">
        <CivicMapSvg />
      </div>
    </div>
  );
}
