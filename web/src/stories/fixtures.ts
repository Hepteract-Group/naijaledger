import type { NarrativeStory } from "./types";

/** Illustrative demo only — not a published claim. */
export const DEMO_STORY: NarrativeStory = {
  slug: "follow-the-ledger",
  title: "Follow the ledger",
  lede: "How NaijaLedger turns archived public records into a cited narrative — without auto-publishing accusations.",
  demo: true,
  next: { label: "Explore parties", to: "/explore" },
  steps: [
    {
      id: "source",
      headline: "Start from a public source",
      body: "Every figure begins as a registered source: a budget PDF, procurement release, or payment schedule. The fetch is archived with a content hash so later readers can prove what was retrieved.",
      visual: {
        kind: "placeholder",
        title: "Source registry",
        detail: "Catalogued URL · cadence · last success hash",
      },
      citations: [{ id: "c1", label: "Source registry (design)", href: "/sources" }],
    },
    {
      id: "extract",
      headline: "Extract with provenance",
      body: "Structured fields keep a pointer back to the page or region they came from. Without that link, a number cannot enter the public narrative path.",
      visual: {
        kind: "stat",
        title: "Provenance rule",
        value: "1∶1",
        detail: "Every datum → document + region",
      },
      citations: [{ id: "c2", label: "Provenance model", href: "/sources" }],
    },
    {
      id: "review",
      headline: "Human review before publish",
      body: "Agents may draft stories and check citation hygiene. Only a human approve_publish decision can surface a claim as public fact — AI proposes, humans dispose.",
      visual: {
        kind: "quote",
        title: "Publication gate",
        detail: "AI proposes. Humans dispose — for published claims.",
      },
      citations: [{ id: "c3", label: "Review decisions (E8.3)" }],
    },
    {
      id: "disclose",
      headline: "Disclose progressively",
      body: "Readers meet a headline, then this scroll narrative, then explorable data, then the archived source. Each layer adds evidence without burying the story.",
      visual: {
        kind: "stat",
        title: "Disclosure path",
        value: "4",
        detail: "Headline → story → dashboard → source",
      },
      citations: [
        { id: "c4", label: "Explore parties", href: "/explore" },
        { id: "c5", label: "Sources", href: "/sources" },
      ],
    },
  ],
};

const STORIES: NarrativeStory[] = [DEMO_STORY];

export function listStories(): NarrativeStory[] {
  return STORIES;
}

export function getStory(slug: string): NarrativeStory | undefined {
  return STORIES.find((story) => story.slug === slug);
}
