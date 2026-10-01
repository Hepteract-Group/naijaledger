import { motion, useReducedMotion } from "motion/react";
import { Link } from "react-router-dom";
import { NigeriaConstellation } from "../components/NigeriaConstellation";

function Strip({
  kicker,
  titleId,
  title,
  body,
  to,
  cta,
  visualClass,
  reverse,
  quote,
}: {
  kicker: string;
  titleId: string;
  title: string;
  body: string;
  to: string;
  cta: string;
  visualClass: string;
  reverse?: boolean;
  quote?: string;
}) {
  const reduce = useReducedMotion();
  return (
    <motion.section
      className="home-strip"
      aria-labelledby={titleId}
      initial={reduce ? false : { opacity: 0, y: 28 }}
      whileInView={reduce ? undefined : { opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.35 }}
      transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className={`home-strip__inner${reverse ? " home-strip__inner--reverse" : ""}`}>
        <div>
          <p className="home-strip__kicker">{kicker}</p>
          <h2 id={titleId} className="home-strip__title">
            {title}
          </h2>
          <p className="home-strip__body">{body}</p>
          <Link className="btn btn--ghost" to={to}>
            {cta}
          </Link>
        </div>
        <div className={`home-strip__visual ${visualClass}`} aria-hidden>
          {quote ? <p className="home-strip__quote">{quote}</p> : null}
        </div>
      </div>
    </motion.section>
  );
}

export function HomePage() {
  return (
    <>
      <section className="home-hero" aria-label="Introduction">
        <div className="home-hero__canvas" aria-hidden>
          <NigeriaConstellation />
        </div>
        <div className="home-hero__veil" aria-hidden />
        <div className="home-hero__copy">
          <p className="home-hero__brand">NaijaLedger</p>
          <h1 className="home-hero__headline">Follow the money. Verify the vote.</h1>
          <p className="home-hero__lede">
            Source-backed public finance for Nigeria — evidence first, claims only after human
            review.
          </p>
          <div className="home-hero__actions">
            <Link className="btn btn--primary" to="/explore">
              Explore the ledger
            </Link>
            <Link className="btn btn--ghost" to="/map">
              Open the map
            </Link>
          </div>
        </div>
      </section>

      <Strip
        kicker="Geography"
        titleId="home-map-title"
        title="Drill from federation to state to year"
        body="Contract volume and anomaly density across Nigeria — filter by state, LGA, and fiscal year, then jump into the underlying parties and tenders."
        to="/map"
        cta="Explore the map"
        visualClass="home-strip__visual--map"
      />
      <Strip
        kicker="Relationships"
        titleId="home-graph-title"
        title="See who connects to what"
        body="Agencies, companies, tenders, awards, and contracts as a living graph — built so investigators can chase ownership and concentration, not just rows."
        to="/graph"
        cta="Open the graph"
        visualClass="home-strip__visual--graph"
        reverse
      />
      <Strip
        kicker="Narratives"
        titleId="home-story-title"
        title="Read the story. Check the source."
        body="Scrollytelling investigations with citations on every claim. Demo pieces are labelled until a human approves publication."
        to="/stories"
        cta="Read stories"
        visualClass="home-strip__visual--story"
        quote="Every figure cites an archived document."
      />

      <section className="home-close" aria-labelledby="home-method-title">
        <h2 id="home-method-title" className="home-close__title">
          Built for trust, not theatre
        </h2>
        <p className="home-close__body">
          Capture and hash before parse. Provenance on every datum. Humans gate anything published
          as fact. That is the product.
        </p>
        <Link className="btn btn--primary" to="/methodology">
          How verification works
        </Link>
      </section>
    </>
  );
}
