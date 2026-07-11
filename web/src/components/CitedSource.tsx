import { Link } from "react-router-dom";
import type { Citation } from "../dossier/types";

type CitedSourceProps = {
  citation: Citation;
};

export function CitedSource({ citation }: CitedSourceProps) {
  const body = (
    <>
      <span className="cited-source__label">{citation.label}</span>
      {citation.kind ? <span className="cited-source__kind">{citation.kind}</span> : null}
    </>
  );

  if (citation.href?.startsWith("/")) {
    return (
      <Link className="cited-source" to={citation.href} title={citation.note}>
        {body}
      </Link>
    );
  }
  if (citation.href) {
    return (
      <a
        className="cited-source"
        href={citation.href}
        rel="noreferrer"
        target="_blank"
        title={citation.note}
      >
        {body}
      </a>
    );
  }
  return (
    <span className="cited-source cited-source--plain" title={citation.note}>
      {body}
    </span>
  );
}
