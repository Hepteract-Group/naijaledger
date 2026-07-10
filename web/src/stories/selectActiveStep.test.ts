import { describe, expect, it } from "vitest";
import { selectActiveStep } from "./selectActiveStep";
import { getStory, listStories } from "./fixtures";

describe("selectActiveStep", () => {
  it("picks the highest intersection ratio", () => {
    expect(
      selectActiveStep(
        [
          { id: "a", ratio: 0.2 },
          { id: "b", ratio: 0.8 },
          { id: "c", ratio: 0.1 },
        ],
        "a",
      ),
    ).toBe("b");
  });

  it("keeps the first winner on ties and falls back when empty", () => {
    expect(
      selectActiveStep(
        [
          { id: "a", ratio: 0.5 },
          { id: "b", ratio: 0.5 },
        ],
        "fallback",
      ),
    ).toBe("a");
    expect(selectActiveStep([], "fallback")).toBe("fallback");
  });
});

describe("story fixtures", () => {
  it("lists the demo story and resolves by slug", () => {
    const stories = listStories();
    expect(stories.length).toBeGreaterThanOrEqual(1);
    expect(stories[0]?.demo).toBe(true);
    expect(getStory("follow-the-ledger")?.steps.length).toBeGreaterThanOrEqual(2);
    expect(getStory("missing")).toBeUndefined();
  });
});
