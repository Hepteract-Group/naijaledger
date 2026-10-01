import { Link } from "react-router-dom";

export function MethodologyPage() {
  return (
    <div className="page">
      <p className="page__kicker">Trust model</p>
      <h1 className="page__title">How verification works</h1>
      <p className="page__lede">
        NaijaLedger is built so a published number can be traced to a document, a fetch, and a human
        decision. The UI never invents authority the pipeline does not have.
      </p>

      <ol className="method-list">
        <li>
          <h2>Capture before parse</h2>
          <p>
            Raw bytes are hashed and written to a write-once archive the moment we can reach a
            source. Extraction happens after. If the portal disappears later, the evidence remains.
          </p>
        </li>
        <li>
          <h2>Provenance on every datum</h2>
          <p>
            Canonical values link back to source document, page or region, and fetch record. Charts
            and stories are meant to cite that chain — not float free.
          </p>
        </li>
        <li>
          <h2>Hypotheses are not verdicts</h2>
          <p>
            Anomaly flags are open questions with evidence. They stay labelled until a human review
            decision allows publication as fact.
          </p>
        </li>
        <li>
          <h2>Demo vs live, always labelled</h2>
          <p>
            When the API is empty or unreachable, the UI may show illustrative fixtures so the
            product is usable. Those surfaces carry an explicit demo banner.
          </p>
        </li>
      </ol>

      <div className="method-cta">
        <Link className="btn btn--primary" to="/sources">
          Browse sources
        </Link>
        <Link className="btn btn--ghost" to="/explore">
          Explore data
        </Link>
      </div>
    </div>
  );
}
