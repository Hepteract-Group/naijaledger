import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchStoryBySlug, toNarrativeStory } from "../api/stories";
import { ScrollyStory } from "../components/ScrollyStory";
import { getStory } from "../stories/fixtures";
import type { NarrativeStory } from "../stories/types";

type LoadState =
  | { kind: "loading" }
  | { kind: "live"; story: NarrativeStory }
  | { kind: "demo"; story: NarrativeStory }
  | { kind: "missing" };

export function StoryPage() {
  const { slug = "" } = useParams();
  const [load, setLoad] = useState<LoadState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    setLoad({ kind: "loading" });
    void fetchStoryBySlug(slug)
      .then((pub) => {
        if (!cancelled) {
          setLoad({ kind: "live", story: toNarrativeStory(pub) });
        }
      })
      .catch(() => {
        if (cancelled) {
          return;
        }
        const demo = getStory(slug);
        if (demo) {
          setLoad({ kind: "demo", story: demo });
          return;
        }
        setLoad({ kind: "missing" });
      });
    return () => {
      cancelled = true;
    };
  }, [slug]);

  if (load.kind === "loading") {
    return (
      <div className="page">
        <h1 className="page__title">Loading story…</h1>
      </div>
    );
  }

  if (load.kind === "missing") {
    return (
      <div className="page">
        <h1 className="page__title">Story not found</h1>
        <p className="page__lede">No narrative is registered for “{slug}”.</p>
        <Link className="btn btn--ghost" to="/stories">
          Back to stories
        </Link>
      </div>
    );
  }

  return (
    <div className="page page--story">
      <ScrollyStory story={load.story} />
    </div>
  );
}
