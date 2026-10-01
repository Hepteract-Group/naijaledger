import { useEffect, useId, useRef, useState, type ReactNode } from "react";

type InfoTipProps = {
  label: string;
  children: ReactNode;
};

function canHoverFinePointer(): boolean {
  return window.matchMedia("(hover: hover) and (pointer: fine)").matches;
}

/** Compact help: hover on fine pointers; tap/keyboard toggle elsewhere. Escape dismisses. */
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
        onMouseEnter={() => {
          if (canHoverFinePointer()) {
            setOpen(true);
          }
        }}
        onMouseLeave={() => {
          if (canHoverFinePointer()) {
            setOpen(false);
          }
        }}
        onClick={() => {
          // Fine-pointer devices already open on hover; ignore click so we do not flash closed.
          if (canHoverFinePointer()) {
            return;
          }
          setOpen((value) => !value);
        }}
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
