import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchStories } from "../api/stories";
import { listStories } from "../stories/fixtures";
import type { NarrativeStory } from "../stories/types";

type LoadState =
  | { kind: "loading" }
  | { kind: "live"; stories: NarrativeStory[] }
  | { kind: "demo"; stories: NarrativeStory[]; reason: string };

export function StoriesIndexPage() {
  const [load, setLoad] = useState<LoadState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    setLoad({ kind: "loading" });
    void fetchStories()
      .then((page) => {
        if (cancelled) {
          return;
        }
        if (page.items.length === 0) {
          setLoad({
            kind: "demo",
            stories: listStories(),
            reason: "No published stories yet",
          });
          return;
        }
        setLoad({
          kind: "live",
          stories: page.items.map((item) => ({
            slug: item.slug,
            title: item.title,
            lede: item.lede,
            demo: false,
            steps: item.steps,
            next: item.next,
          })),
        });
      })
      .catch((error: unknown) => {
        if (cancelled) {
          return;
        }
        const reason = error instanceof Error ? error.message : "API unavailable";
        setLoad({ kind: "demo", stories: listStories(), reason });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const stories = load.kind === "loading" ? [] : load.stories;

  return (
    <div className="page">
      <h1 className="page__title">Stories</h1>
      <p className="page__lede">
        Cited narrative investigations. Demo stories are labelled until human-approved publication
        is available.
      </p>
      {load.kind === "demo" ? (
        <p className="scrolly__demo-banner" role="status">
          Showing demo narratives ({load.reason}).
        </p>
      ) : null}
      {load.kind === "loading" ? <p className="page__lede">Loading stories…</p> : null}
      <ul className="story-index">
        {stories.map((story) => (
          <li key={story.slug} className="story-index__item">
            <Link className="story-index__link" to={`/stories/${story.slug}`}>
              <span className="story-index__title">{story.title}</span>
              {story.demo ? <span className="story-index__badge">Demo</span> : null}
            </Link>
            <p className="story-index__lede">{story.lede}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}
