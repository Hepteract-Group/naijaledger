import { apiGet } from "./client";
import type { NarrativeStory } from "../stories/types";

export type PublicStory = NarrativeStory & {
  id: string;
  published_at: string;
  demo: false;
};

export type StoriesPage = {
  items: PublicStory[];
  limit: number;
  offset: number;
  count: number;
};

export function fetchStories(
  params: { limit?: number; offset?: number } = {},
): Promise<StoriesPage> {
  const search = new URLSearchParams();
  if (params.limit != null) {
    search.set("limit", String(params.limit));
  }
  if (params.offset != null) {
    search.set("offset", String(params.offset));
  }
  const query = search.toString();
  return apiGet<StoriesPage>(`/v1/stories${query ? `?${query}` : ""}`);
}

export function fetchStoryBySlug(slug: string): Promise<PublicStory> {
  return apiGet<PublicStory>(`/v1/stories/by-slug/${encodeURIComponent(slug)}`);
}

export function toNarrativeStory(story: PublicStory): NarrativeStory {
  return {
    slug: story.slug,
    title: story.title,
    lede: story.lede,
    demo: false,
    steps: story.steps,
    next: story.next,
  };
}
