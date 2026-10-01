import { Link } from "react-router-dom";
import { InfoTip } from "../components/InfoTip";

export function MethodologyPage() {
  return (
    <div className="page">
      <p className="page__kicker">Why trust this</p>
      <h1 className="page__title">We verify before we speak</h1>
      <p className="page__lede">
        Public anger without receipts burns out. NaijaLedger is built so every figure you meet can
        be walked back to a document someone archived — and every public claim waits for a human.
      </p>

      <ol className="method-list">
        <li>
          <h2>Save the original first</h2>
          <p>
            When we reach a government page or file, we store the exact bytes and a fingerprint
            before anyone reads the numbers. Portals go dark. Receipts should not.
            <InfoTip label="Technical name">
              This is our write-once archive — content-hashed so tampering is obvious.
            </InfoTip>
          </p>
        </li>
        <li>
          <h2>Keep the trail attached</h2>
          <p>
            A number without a page is just a rumour with formatting. Each value we keep points at
            the document and place it came from.
          </p>
        </li>
        <li>
          <h2>Questions are not verdicts</h2>
          <p>
            Odd patterns become flags for people to review. We do not auto-publish accusations.
            Machines propose; humans dispose.
          </p>
        </li>
        <li>
          <h2>Say when something is a demo</h2>
          <p>
            If live data is thin, we may show labelled examples so you can still learn the
            interface. Look for the Demo badge
            <InfoTip label="Demo vs live">
              Live means the public API answered. Demo means illustrative sample data.
            </InfoTip>
            .
          </p>
        </li>
      </ol>

      <div className="method-cta">
        <Link className="btn btn--primary" to="/sources">
          See the sources
        </Link>
        <Link className="btn btn--ghost" to="/explore">
          Enter the ledger
        </Link>
      </div>
    </div>
  );
}
