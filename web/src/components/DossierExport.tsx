import type { Citation } from "../dossier/types";
import { buildDossier, dossierToJson, dossierToMarkdown, downloadTextFile } from "../dossier/types";

type DossierExportProps = {
  title: string;
  items: readonly Citation[];
  demo?: boolean;
  slug?: string;
};

export function DossierExport({
  title,
  items,
  demo = false,
  slug = "dossier",
}: DossierExportProps) {
  const exportJson = () => {
    const dossier = buildDossier({ title, items, demo });
    downloadTextFile(`${slug}.json`, dossierToJson(dossier), "application/json");
  };

  const exportMarkdown = () => {
    const dossier = buildDossier({ title, items, demo });
    downloadTextFile(`${slug}.md`, dossierToMarkdown(dossier), "text/markdown");
  };

  return (
    <div className="dossier-export">
      <p className="dossier-export__label">Export dossier</p>
      {demo ? (
        <p className="dossier-export__note">
          Illustrative demo pack — not a published evidence file.
        </p>
      ) : null}
      <div className="dossier-export__actions">
        <button type="button" className="btn btn--ghost" onClick={exportJson}>
          Download JSON
        </button>
        <button type="button" className="btn btn--ghost" onClick={exportMarkdown}>
          Download Markdown
        </button>
      </div>
    </div>
  );
}
