/** Citation + dossier types (E10.6 / spec 0031). */

export type Citation = {
  id: string;
  label: string;
  href?: string;
  kind?: string;
  note?: string;
};

export type Dossier = {
  title: string;
  generated_at: string;
  demo: boolean;
  items: Citation[];
};

export function buildDossier(input: {
  title: string;
  demo?: boolean;
  items: readonly Citation[];
  now?: () => string;
}): Dossier {
  const seen = new Set<string>();
  const items: Citation[] = [];
  for (const item of input.items) {
    if (seen.has(item.id)) {
      continue;
    }
    seen.add(item.id);
    items.push(item);
  }
  return {
    title: input.title,
    generated_at: (input.now ?? (() => new Date().toISOString()))(),
    demo: input.demo ?? false,
    items,
  };
}

export function dossierToJson(dossier: Dossier): string {
  return `${JSON.stringify(dossier, null, 2)}\n`;
}

export function dossierToMarkdown(dossier: Dossier): string {
  const lines = [
    `# ${dossier.title}`,
    "",
    `Generated: ${dossier.generated_at}`,
    dossier.demo ? "Status: illustrative demo — not a published evidence pack." : "Status: export",
    "",
    "## Citations",
    "",
  ];
  for (const item of dossier.items) {
    const link = item.href ? ` — ${item.href}` : "";
    const kind = item.kind ? ` (${item.kind})` : "";
    const note = item.note ? ` — ${item.note}` : "";
    lines.push(`- **${item.label}**${kind}${link}${note}`);
  }
  if (dossier.items.length === 0) {
    lines.push("- _(none)_");
  }
  lines.push("");
  return lines.join("\n");
}

export function downloadTextFile(filename: string, contents: string, mime: string): void {
  const blob = new Blob([contents], { type: mime });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  window.setTimeout(() => {
    URL.revokeObjectURL(url);
  }, 0);
}
