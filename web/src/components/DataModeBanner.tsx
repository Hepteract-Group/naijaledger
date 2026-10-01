type DataModeBannerProps = {
  mode: "demo" | "live";
  message: string;
};

export function DataModeBanner({ mode, message }: DataModeBannerProps) {
  return (
    <p className={`data-banner data-banner--${mode}`} role="status">
      <span className="data-banner__pill">{mode === "demo" ? "Demo" : "Live"}</span>
      <span>{message}</span>
    </p>
  );
}
