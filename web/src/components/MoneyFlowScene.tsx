import { useEffect, useRef } from "react";
import {
  motion,
  useMotionValueEvent,
  useReducedMotion,
  useScroll,
  useSpring,
  useTransform,
  type MotionValue,
} from "motion/react";

type Particle = {
  x: number;
  y: number;
  vx: number;
  vy: number;
  r: number;
  gold: boolean;
};

/** Soft ambient particle field — backdrop only. */
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
      vx: (Math.random() - 0.25) * 0.35,
      vy: (Math.random() - 0.5) * 0.2,
      r: 0.7 + Math.random() * 1.8,
      gold: Math.random() > 0.6,
    });

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = canvas.clientWidth;
      height = canvas.clientHeight;
      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      particles = Array.from({ length: reduce ? 16 : 70 }, () => spawn(width, height));
    };

    const tick = () => {
      const t = Math.min(1, Math.max(0, progressRef.current));
      ctx.clearRect(0, 0, width, height);

      const g = ctx.createRadialGradient(
        width * 0.72,
        height * 0.4,
        10,
        width * 0.6,
        height * 0.5,
        Math.max(width, height) * 0.7,
      );
      g.addColorStop(0, `hsla(158, 55%, 40%, ${0.12 + t * 0.1})`);
      g.addColorStop(0.55, "hsla(210, 30%, 12%, 0.06)");
      g.addColorStop(1, "hsla(150, 15%, 6%, 0)");
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, width, height);

      const speed = reduce ? 0 : 0.55 + t * 1.1;
      for (const p of particles) {
        if (!reduce) {
          p.x += p.vx * speed;
          p.y += p.vy * speed;
          if (p.x < -10) p.x = width + 10;
          if (p.x > width + 10) p.x = -10;
          if (p.y < -10) p.y = height + 10;
          if (p.y > height + 10) p.y = -10;
        }
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = p.gold
          ? `hsla(42, 80%, 58%, ${0.22 + t * 0.2})`
          : `hsla(158, 70%, 55%, ${0.2 + t * 0.22})`;
        ctx.fill();
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

/** Abstracted ledger folios: source document → money entry → proof status. */
const FOLIOS = [
  {
    key: "source",
    folio: "A",
    label: "Source",
    rows: [
      { k: "Doc", v: "NOCOPO · sealed" },
      { k: "When", v: "fetched · archived" },
      { k: "Hash", v: "a3f9…c21e" },
    ],
    className: "ledger-panel--archive",
  },
  {
    key: "entry",
    folio: "B",
    label: "Entry",
    rows: [
      { k: "From", v: "Ministry of Works" },
      { k: "To", v: "Contractor Ltd" },
      { k: "Amt", v: "₦2.4bn · FY24" },
    ],
    className: "ledger-panel--trail",
  },
  {
    key: "proof",
    folio: "C",
    label: "Proof",
    rows: [
      { k: "Cite", v: "p.14 · region B" },
      { k: "Gate", v: "human review" },
      { k: "Out", v: "held · not claim" },
    ],
    className: "ledger-panel--claim",
  },
] as const;

/**
 * 3D living ledger: three glass folios in perspective.
 * Source → Entry → Proof. Scroll tilts the book.
 */
export function LivingLedger() {
  const reduce = useReducedMotion();
  const stageRef = useRef<HTMLDivElement | null>(null);
  const { scrollYProgress } = useScroll({
    target: stageRef,
    offset: ["start start", "end start"],
  });

  const tiltX = useTransform(scrollYProgress, [0, 1], [14, -6]);
  const tiltY = useTransform(scrollYProgress, [0, 1], [-22, 10]);
  const floatY = useTransform(scrollYProgress, [0, 1], [0, 28]);
  const springX = useSpring(tiltX, { stiffness: 60, damping: 22 });
  const springY = useSpring(tiltY, { stiffness: 60, damping: 22 });

  return (
    <div ref={stageRef} className="ledger-stage" aria-hidden>
      <div className="ledger-stage__floor" />
      <motion.div
        className="ledger-rig"
        style={
          reduce
            ? { rotateX: 12, rotateY: -18 }
            : {
                rotateX: springX,
                rotateY: springY,
                y: floatY,
                transformPerspective: 1200,
              }
        }
        animate={
          reduce
            ? undefined
            : {
                rotateZ: [-1.2, 1.2, -1.2],
              }
        }
        transition={
          reduce
            ? undefined
            : { duration: 14, repeat: Infinity, ease: "easeInOut" }
        }
      >
        {FOLIOS.map((panel, index) => (
          <motion.article
            key={panel.key}
            className={`ledger-panel ${panel.className}`}
            initial={reduce ? false : { opacity: 0 }}
            animate={reduce ? undefined : { opacity: 1 }}
            transition={{
              duration: 1.05,
              delay: 0.15 + index * 0.18,
              ease: [0.22, 1, 0.36, 1],
            }}
            style={{
              x: index * 58,
              y: index * -12,
              z: index * 52,
              rotateY: index * -7,
            }}
          >
            <header className="ledger-panel__head">
              <span className="ledger-panel__index">Folio {panel.folio}</span>
              <span className="ledger-panel__label">{panel.label}</span>
            </header>
            <dl className="ledger-panel__rows">
              {panel.rows.map((row) => (
                <div key={row.k} className="ledger-panel__row">
                  <dt>{row.k}</dt>
                  <dd>{row.v}</dd>
                </div>
              ))}
            </dl>
            <div className="ledger-panel__glow" />
          </motion.article>
        ))}

        <svg className="ledger-threads" viewBox="0 0 400 260" aria-hidden>
          <motion.path
            d="M70 80 C140 40, 260 40, 330 90"
            fill="none"
            stroke="var(--gold-bright)"
            strokeWidth="1.4"
            strokeDasharray="5 9"
            animate={reduce ? undefined : { strokeDashoffset: [0, -56] }}
            transition={{ duration: 5.5, repeat: Infinity, ease: "linear" }}
            opacity={0.7}
          />
          <motion.path
            d="M70 140 C150 170, 250 100, 330 150"
            fill="none"
            stroke="var(--accent)"
            strokeWidth="1.4"
            strokeDasharray="5 9"
            animate={reduce ? undefined : { strokeDashoffset: [0, -56] }}
            transition={{ duration: 7, repeat: Infinity, ease: "linear" }}
            opacity={0.65}
          />
          <motion.path
            d="M70 200 C160 220, 240 180, 330 210"
            fill="none"
            stroke="var(--indigo)"
            strokeWidth="1.2"
            strokeDasharray="4 10"
            animate={reduce ? undefined : { strokeDashoffset: [0, -48] }}
            transition={{ duration: 8.5, repeat: Infinity, ease: "linear" }}
            opacity={0.55}
          />
        </svg>
      </motion.div>
    </div>
  );
}

const SPINE_NODES = [
  { id: "witness", label: "Witness", top: "12%" },
  { id: "trace", label: "Trace", top: "36%" },
  { id: "relate", label: "Relate", top: "60%" },
  { id: "speak", label: "Speak", top: "84%" },
] as const;

function StoryTrailNode({
  label,
  top,
  index,
  progress,
}: {
  label: string;
  top: string;
  index: number;
  progress: MotionValue<number>;
}) {
  const start = index / SPINE_NODES.length;
  const end = (index + 0.85) / SPINE_NODES.length;
  const opacity = useTransform(progress, [start, end], [0.28, 1]);
  const scale = useTransform(progress, [start, end], [0.86, 1.1]);

  return (
    <motion.div className="story-trail__node" style={{ top, opacity, scale }}>
      <span className="story-trail__orb" />
      <span className="story-trail__caption">{label}</span>
    </motion.div>
  );
}

/**
 * Scroll-linked 3D money trail beside the story chapters.
 * Nodes light as you progress; a bead travels the rail.
 */
export function StoryTrail() {
  const reduce = useReducedMotion();
  const hostRef = useRef<HTMLDivElement | null>(null);
  const { scrollYProgress } = useScroll({
    target: hostRef,
    offset: ["start end", "end start"],
  });
  const rotateY = useTransform(scrollYProgress, [0, 1], [-28, 18]);
  const rotateX = useTransform(scrollYProgress, [0, 1], [8, -12]);
  const beadY = useTransform(scrollYProgress, [0, 1], ["8%", "88%"]);
  const springY = useSpring(rotateY, { stiffness: 50, damping: 20 });
  const springX = useSpring(rotateX, { stiffness: 50, damping: 20 });

  return (
    <div ref={hostRef} className="story-trail" aria-hidden>
      <motion.div
        className="story-trail__rig"
        style={
          reduce
            ? { rotateY: -12, rotateX: 4 }
            : {
                rotateY: springY,
                rotateX: springX,
                transformPerspective: 900,
              }
        }
      >
        <div className="story-trail__rail" />
        {SPINE_NODES.map((node, index) => (
          <StoryTrailNode
            key={node.id}
            label={node.label}
            top={node.top}
            index={index}
            progress={scrollYProgress}
          />
        ))}
        {!reduce ? (
          <motion.span className="story-trail__bead" style={{ top: beadY }} />
        ) : null}
      </motion.div>
    </div>
  );
}

export function MoneyFlowScene() {
  return (
    <div className="money-flow-stage" aria-hidden>
      <ParticleField />
    </div>
  );
}
