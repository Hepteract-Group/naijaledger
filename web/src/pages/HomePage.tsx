import { Link } from "react-router-dom";

export function HomePage() {
  return (
    <section className="hero" aria-label="Introduction">
      <div>
        <p className="hero__brand">NaijaLedger</p>
        <h1 className="hero__headline">Follow the money. Verify the vote.</h1>
        <p className="hero__lede">
          Source-backed public finance and election verification — evidence first, claims only after
          human review.
        </p>
        <div className="hero__actions">
          <Link className="btn btn--primary" to="/explore">
            Explore parties
          </Link>
          <Link className="btn btn--ghost" to="/stories">
            Read stories
          </Link>
        </div>
      </div>
    </section>
  );
}
