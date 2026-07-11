import { describe, expect, it } from "vitest";
import { buildDossier, dossierToJson, dossierToMarkdown } from "./types";

describe("dossier builders", () => {
  it("dedupes citations and serializes json/markdown", () => {
    const dossier = buildDossier({
      title: "Demo pack",
      demo: true,
      now: () => "2026-07-11T00:00:00.000Z",
      items: [
        { id: "a", label: "Source A", href: "/sources" },
        { id: "a", label: "Source A duplicate" },
        { id: "b", label: "Flag note", kind: "hypothesis", note: "open" },
      ],
    });
    expect(dossier.items).toHaveLength(2);
    expect(dossier.generated_at).toBe("2026-07-11T00:00:00.000Z");
    const json = dossierToJson(dossier);
    expect(json).toContain("Demo pack");
    expect(json).toContain('"demo": true');
    const md = dossierToMarkdown(dossier);
    expect(md).toContain("# Demo pack");
    expect(md).toContain("Source A");
    expect(md).toContain("illustrative demo");
  });
});
