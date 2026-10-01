import { motion, useReducedMotion, useScroll, useTransform } from "motion/react";
import { useRef, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { InfoTip } from "../components/InfoTip";
import { LivingLedger, MoneyFlowScene, StoryTrail } from "../components/MoneyFlowScene";

function Chapter({
  id,
  kicker,
  title,
  children,
  cta,
}: {
  id: string;
  kicker: string;
  title: string;
  children: ReactNode;
  cta?: { to: string; label: string };
}) {
  const reduce = useReducedMotion();
  return (
    <motion.section
      className="civic-chapter"
      aria-labelledby={id}
      initial={reduce ? false : { opacity: 0, y: 40 }}
      whileInView={reduce ? undefined : { opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.4 }}
      transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
    >
      <p className="civic-chapter__kicker">{kicker}</p>
      <h2 id={id} className="civic-chapter__title">
        {title}
      </h2>
      <div className="civic-chapter__body">{children}</div>
      {cta ? (
        <Link className="btn btn--ghost" to={cta.to}>
          {cta.label}
        </Link>
      ) : null}
    </motion.section>
  );
}

export function HomePage() {
  const heroRef = useRef<HTMLElement | null>(null);
  const reduce = useReducedMotion();
  const { scrollYProgress } = useScroll({
    target: heroRef,
    offset: ["start start", "end start"],
  });
  const titleY = useTransform(scrollYProgress, [0, 1], [0, reduce ? 0 : 80]);
  const titleOpacity = useTransform(scrollYProgress, [0, 0.75], [1, 0.15]);

  return (
    <div className="civic-home">
      <section ref={heroRef} className="civic-hero" aria-label="Introduction">
        <MoneyFlowScene />
        <div className="civic-hero__veil" />
        <LivingLedger />
        <motion.div className="civic-hero__copy" style={{ y: titleY, opacity: titleOpacity }}>
          <p className="civic-hero__brand">
            NaijaLedger
            <InfoTip label="What is NaijaLedger?">
              An open ledger of Nigeria’s public money — archived at the source, readable by anyone,
              published only after human review.
            </InfoTip>
          </p>
          <h1 className="civic-hero__headline">
            The money is ours.
            <span className="civic-hero__headline-break">The duty is ours.</span>
          </h1>
          <p className="civic-hero__lede">
            Public money leaves a trail. We keep the map. Follow it. Ask questions. Keep the record.
          </p>
          <div className="civic-hero__actions">
            <Link className="btn btn--primary" to="/explore">
              Enter the ledger
            </Link>
            <Link className="btn btn--ghost" to="/methodology">
              Why we verify
            </Link>
          </div>
        </motion.div>
        <motion.p
          className="civic-hero__scroll"
          initial={reduce ? false : { opacity: 0 }}
          animate={reduce ? undefined : { opacity: [0.35, 1, 0.35] }}
          transition={{ duration: 2.4, repeat: Infinity, ease: "easeInOut" }}
        >
          Scroll the story
        </motion.p>
      </section>

      <div className="civic-story">
        <StoryTrail />
        <Chapter id="ch-watch" kicker="01 — Witness" title="Budgets are promises written in ink">
          <p>
            Across Africa, we know the ritual: announcements, ribbon cuttings, then silence.
            NaijaLedger starts where silence usually wins — by capturing the public record before it
            can rot, disappear, or be rewritten.
          </p>
        </Chapter>

        <Chapter
          id="ch-trail"
          kicker="02 — Trace"
          title="From ministry to contract to community"
          cta={{ to: "/map", label: "See it on the map" }}
        >
          <p>
            Money does not vanish. It travels — through agencies, tenders, awards, and companies.
            Explore those paths. Zoom from the federation to your state
            <InfoTip label="How filters work">
              On the map and explore pages, choose a state, LGA, or year to narrow the trail.
            </InfoTip>
            .
          </p>
        </Chapter>

        <Chapter
          id="ch-people"
          kicker="03 — Relate"
          title="Names connect. Patterns appear."
          cta={{ to: "/graph", label: "Open the graph" }}
        >
          <p>
            Who bids together? Who wins repeatedly? The graph is not gossip — it is structure made
            visible, so journalists, organisers, and citizens can ask sharper questions.
          </p>
        </Chapter>

        <Chapter
          id="ch-voice"
          kicker="04 — Speak"
          title="Civic duty is not a spectator sport"
          cta={{ to: "/stories", label: "Read a narrative" }}
        >
          <p>
            Inspiration without evidence is noise. Evidence without courage is a filing cabinet.
            Stories here cite sources. Red flags stay labelled as questions until a human decides
            what may be published as fact
            <InfoTip label="Publication gate">
              We never auto-publish accusations. AI can draft; people approve.
            </InfoTip>
            .
          </p>
        </Chapter>

        <motion.section
          className="civic-close"
          aria-labelledby="civic-close-title"
          initial={reduce ? false : { opacity: 0, scale: 0.98 }}
          whileInView={reduce ? undefined : { opacity: 1, scale: 1 }}
          viewport={{ once: true, amount: 0.5 }}
          transition={{ duration: 0.65, ease: [0.22, 1, 0.36, 1] }}
        >
          <h2 id="civic-close-title" className="civic-close__title">
            Hold the line with us
          </h2>
          <p className="civic-close__body">
            Openness is our security model. Lawful. Nonpartisan. Built so the next generation
            inherits receipts — not rumours.
          </p>
          <div className="civic-hero__actions">
            <Link className="btn btn--primary" to="/explore">
              Start exploring
            </Link>
            <Link className="btn btn--ghost" to="/sources">
              Meet the sources
            </Link>
          </div>
        </motion.section>
      </div>
    </div>
  );
}
