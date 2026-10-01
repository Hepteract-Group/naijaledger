import { useEffect, useId, useRef, useState, type ReactNode } from "react";

type InfoTipProps = {
  label: string;
  children: ReactNode;
};

/** Compact help: hover, focus, or tap. Escape dismisses. */
export function InfoTip({ label, children }: InfoTipProps) {
  const tipId = useId();
  const rootRef = useRef<HTMLSpanElement | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) {
      return;
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };
    const onPointerDown = (event: PointerEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("pointerdown", onPointerDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("pointerdown", onPointerDown);
    };
  }, [open]);

  return (
    <span ref={rootRef} className="info-tip">
      <button
        type="button"
        className="info-tip__btn"
        aria-describedby={open ? tipId : undefined}
        aria-label={label}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onClick={() => setOpen((value) => !value)}
      >
        i
      </button>
      {open ? (
        <span id={tipId} role="tooltip" className="info-tip__panel">
          {children}
        </span>
      ) : null}
    </span>
  );
}
