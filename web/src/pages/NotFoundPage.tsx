import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <div className="page page--center">
      <p className="page__kicker">404</p>
      <h1 className="page__title">This trail ends here</h1>
      <p className="page__lede">
        That URL is not a page in NaijaLedger. Head back to the ledger, the map, or the method.
      </p>
      <div className="page__actions">
        <Link className="btn btn--primary" to="/">
          Home
        </Link>
        <Link className="btn btn--ghost" to="/explore">
          Explore
        </Link>
        <Link className="btn btn--ghost" to="/methodology">
          Methodology
        </Link>
      </div>
    </div>
  );
}
