import { Link } from "react-router-dom";
import { useActiveStep } from "../hooks/useActiveStep";
import type { NarrativeStory, StoryStep, StoryVisual } from "../stories/types";

type ScrollyStoryProps = {
  story: NarrativeStory;
};

function StoryVisualPanel({ visual, active }: { visual: StoryVisual; active: boolean }) {
  return (
    <div
      className={`scrolly__visual-card${active ? " scrolly__visual-card--active" : ""}`}
      aria-hidden={!active}
    >
      {visual.kind === "stat" ? (
        <>
          <p className="scrolly__visual-kicker">{visual.title}</p>
          <p className="scrolly__visual-value">{visual.value}</p>
          {visual.detail ? <p className="scrolly__visual-detail">{visual.detail}</p> : null}
        </>
      ) : null}
      {visual.kind === "quote" ? (
        <>
          <p className="scrolly__visual-kicker">{visual.title}</p>
          <blockquote className="scrolly__visual-quote">{visual.detail}</blockquote>
        </>
      ) : null}
      {visual.kind === "placeholder" ? (
        <>
          <p className="scrolly__visual-kicker">{visual.title}</p>
          {visual.detail ? <p className="scrolly__visual-detail">{visual.detail}</p> : null}
          <p className="scrolly__visual-hint">Visual placeholder — charts/maps arrive in E10.3+</p>
        </>
      ) : null}
    </div>
  );
}

function StepCitations({ step }: { step: StoryStep }) {
  if (step.citations.length === 0) {
    return null;
  }
  return (
    <ul className="scrolly__citations" aria-label="Citations">
      {step.citations.map((citation) => (
        <li key={citation.id}>
          {citation.href ? (
            <Link to={citation.href}>{citation.label}</Link>
          ) : (
            <span>{citation.label}</span>
          )}
        </li>
      ))}
    </ul>
  );
}

export function ScrollyStory({ story }: ScrollyStoryProps) {
  const stepIds = story.steps.map((step) => step.id);
  const activeId = useActiveStep(stepIds);
  const activeStep = story.steps.find((step) => step.id === activeId) ?? story.steps[0];
  const activeIndex = Math.max(
    0,
    story.steps.findIndex((step) => step.id === activeId),
  );
  const progress = story.steps.length > 0 ? (activeIndex + 1) / story.steps.length : 0;

  return (
    <article className="scrolly">
      <header className="scrolly__header">
        {story.demo ? (
          <p className="scrolly__demo-banner" role="status">
            Illustrative demo — not a published claim.
          </p>
        ) : null}
        <h1 className="scrolly__title">{story.title}</h1>
        <p className="scrolly__lede">{story.lede}</p>
        <div
          className="scrolly__progress"
          role="progressbar"
          aria-valuemin={1}
          aria-valuemax={story.steps.length}
          aria-valuenow={activeIndex + 1}
          aria-label="Story progress"
        >
          <div className="scrolly__progress-bar" style={{ width: `${progress * 100}%` }} />
        </div>
      </header>

      <div className="scrolly__layout">
        <div className="scrolly__steps">
          {story.steps.map((step) => {
            const isActive = step.id === activeId;
            return (
              <section
                key={step.id}
                className={`scrolly__step${isActive ? " scrolly__step--active" : ""}`}
                data-step-id={step.id}
                aria-current={isActive ? "step" : undefined}
              >
                <h2 className="scrolly__step-headline">{step.headline}</h2>
                <p className="scrolly__step-body">{step.body}</p>
                <StepCitations step={step} />
              </section>
            );
          })}
        </div>

        <aside className="scrolly__visual" aria-live="polite">
          <div className="scrolly__visual-sticky">
            {activeStep ? (
              <StoryVisualPanel key={activeStep.id} visual={activeStep.visual} active />
            ) : null}
          </div>
        </aside>
      </div>

      <footer className="scrolly__footer">
        <p className="scrolly__footer-label">Continue</p>
        <Link className="btn btn--primary" to={story.next.to}>
          {story.next.label}
        </Link>
        <Link className="btn btn--ghost" to="/sources">
          Browse sources
        </Link>
      </footer>
    </article>
  );
}
