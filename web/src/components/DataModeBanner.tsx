type DataModeBannerProps = {
  mode: "demo" | "live" | "empty";
  message: string;
};

const PILL: Record<DataModeBannerProps["mode"], string> = {
  demo: "Demo",
  live: "Live",
  empty: "Empty",
};

export function DataModeBanner({ mode, message }: DataModeBannerProps) {
  return (
    <p className={`data-banner data-banner--${mode}`} role="status">
      <span className="data-banner__pill">{PILL[mode]}</span>
      <span>{message}</span>
    </p>
  );
}
