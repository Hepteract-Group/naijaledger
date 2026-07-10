import type { CountBucket } from "../explore/helpers";

type DistributionChartProps = {
  title: string;
  buckets: CountBucket[];
};

export function DistributionChart({ title, buckets }: DistributionChartProps) {
  const max = buckets.reduce((acc, bucket) => Math.max(acc, bucket.count), 0);

  return (
    <section className="dist-chart" aria-label={title}>
      <h2 className="dist-chart__title">{title}</h2>
      {buckets.length === 0 || max === 0 ? (
        <p className="dist-chart__empty">No distribution yet.</p>
      ) : (
        <ul className="dist-chart__list">
          {buckets.map((bucket) => {
            const width = `${(bucket.count / max) * 100}%`;
            return (
              <li key={bucket.key} className="dist-chart__row">
                <span className="dist-chart__label">{bucket.key}</span>
                <span className="dist-chart__track" aria-hidden>
                  <span className="dist-chart__bar" style={{ width }} />
                </span>
                <span className="dist-chart__count">{bucket.count}</span>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
