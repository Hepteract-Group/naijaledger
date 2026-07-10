/** Pure helper: pick the step with the highest intersection ratio (ties → first). */

export type StepIntersection = {
  id: string;
  ratio: number;
};

export function selectActiveStep(
  intersections: readonly StepIntersection[],
  fallbackId: string,
): string {
  let bestId = fallbackId;
  let bestRatio = -1;
  for (const entry of intersections) {
    if (entry.ratio > bestRatio) {
      bestRatio = entry.ratio;
      bestId = entry.id;
    }
  }
  return bestId;
}
