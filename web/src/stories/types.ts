/** Typed narrative story document for scrollytelling (E10.2 / spec 0027). */

export type StoryCitation = {
  id: string;
  label: string;
  href?: string;
};

export type StoryVisual =
  | { kind: "stat"; title: string; value: string; detail?: string }
  | { kind: "quote"; title: string; detail: string }
  | { kind: "placeholder"; title: string; detail?: string };

export type StoryStep = {
  id: string;
  headline: string;
  body: string;
  visual: StoryVisual;
  citations: StoryCitation[];
};

export type NarrativeStory = {
  slug: string;
  title: string;
  lede: string;
  demo: boolean;
  steps: StoryStep[];
  next: { label: string; to: string };
};
