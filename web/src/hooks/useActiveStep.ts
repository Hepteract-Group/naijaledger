import { useEffect, useState } from "react";
import { selectActiveStep } from "../stories/selectActiveStep";

/**
 * Tracks which step id is most visible in the viewport center band.
 * Falls back to the first id when nothing intersects yet.
 */
export function useActiveStep(stepIds: readonly string[]): string {
  const fallback = stepIds[0] ?? "";
  const [activeId, setActiveId] = useState(fallback);
  const stepKey = stepIds.join("|");

  useEffect(() => {
    const ids = stepKey.length > 0 ? stepKey.split("|") : [];
    if (ids.length === 0) {
      return;
    }

    const ratios = new Map<string, number>();
    for (const id of ids) {
      ratios.set(id, 0);
    }

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const id = (entry.target as HTMLElement).dataset.stepId;
          if (!id) {
            continue;
          }
          ratios.set(id, entry.isIntersecting ? entry.intersectionRatio : 0);
        }
        const next = selectActiveStep(
          [...ratios.entries()].map(([id, ratio]) => ({ id, ratio })),
          ids[0] ?? "",
        );
        setActiveId(next);
      },
      {
        root: null,
        // Center band: step becomes active when it crosses mid-viewport.
        rootMargin: "-35% 0px -45% 0px",
        threshold: [0, 0.25, 0.5, 0.75, 1],
      },
    );

    for (const id of ids) {
      // Step ids are controlled slugs (no CSS.escape — jsdom lacks CSS).
      const el = document.querySelector(`[data-step-id="${id}"]`);
      if (el) {
        observer.observe(el);
      }
    }

    return () => {
      observer.disconnect();
    };
  }, [stepKey]);

  return activeId || fallback;
}
