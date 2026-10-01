import { useId, useState, type ReactNode } from "react";

type InfoTipProps = {
  label: string;
  children: ReactNode;
};

/** Compact help: visible on hover/focus, not as page wallpaper. */
export function InfoTip({ label, children }: InfoTipProps) {
  const tipId = useId();
  const [open, setOpen] = useState(false);

  return (
    <span className="info-tip">
      <button
        type="button"
        className="info-tip__btn"
        aria-describedby={open ? tipId : undefined}
        aria-expanded={open}
        aria-label={label}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
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
