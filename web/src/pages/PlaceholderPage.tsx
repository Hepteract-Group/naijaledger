type PlaceholderPageProps = {
  title: string;
  lede: string;
  next: string;
};

export function PlaceholderPage({ title, lede, next }: PlaceholderPageProps) {
  return (
    <div className="page">
      <h1 className="page__title">{title}</h1>
      <p className="page__lede">{lede}</p>
      <p className="placeholder">Coming in {next}.</p>
    </div>
  );
}
