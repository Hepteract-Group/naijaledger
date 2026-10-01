import { Link } from "react-router-dom";
import { InfoTip } from "../components/InfoTip";

export function MethodologyPage() {
  return (
    <div className="page">
      <p className="page__kicker">How verification works</p>
      <h1 className="page__title">From public file to trusted figure</h1>
      <p className="page__lede">
        NaijaLedger does not ask you to trust a spreadsheet. It asks you to follow a chain: archive
        the original, extract with a pointer back to the page, connect the entities, flag odd
        patterns as questions, and only then let a human clear anything for publication.
      </p>

      <ol className="method-list">
        <li>
          <h2>Archive before we read</h2>
          <p>
            The moment we can reach a public source, we store the exact bytes and a content hash in
            a write-once archive. Parsing comes after. If the portal vanishes tomorrow, the evidence
            is still here
            <InfoTip label="Why hash?">
              A SHA-256 fingerprint means anyone can prove the file we show is the same one we
              fetched — not an edited copy.
            </InfoTip>
            .
          </p>
        </li>
        <li>
          <h2>Extract with a citation built in</h2>
          <p>
            Numbers leave the document only when they still know where they came from — document,
            page or region, and fetch record. No orphan figures. No “someone said so.”
          </p>
        </li>
        <li>
          <h2>Normalize and name the actors</h2>
          <p>
            Procurement lands in Open Contracting shapes where we can: parties, tenders, awards,
            contracts. The same ministry or company under five spellings is resolved toward one
            identity so the graph and the map mean something.
          </p>
        </li>
        <li>
          <h2>Score patterns, never publish guilt</h2>
          <p>
            Rules look for things like single-bidder awards, tiny bidding windows, or repeat
            winners. Those become <strong>flags</strong> — hypotheses with evidence. Machines
            propose. Humans dispose. Nothing is surfaced as fact without a review decision.
          </p>
        </li>
        <li>
          <h2>Disclose in layers</h2>
          <p>
            Readers meet a headline, then a cited story, then the explorables, then the archived
            source. Each step adds proof. You should always be able to walk backward to the file we
            saved.
          </p>
        </li>
      </ol>

      <div className="method-cta">
        <Link className="btn btn--primary" to="/sources">
          See what we watch
        </Link>
        <Link className="btn btn--ghost" to="/explore">
          Enter the ledger
        </Link>
      </div>
    </div>
  );
}
