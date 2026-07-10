/** Pure explore helpers (E10.3 / spec 0028). */

export type ExploreResource = "parties" | "tenders" | "flags";

export type SortDir = "asc" | "desc";

export type CountBucket = { key: string; count: number };

export function toggleCompareSelection(selected: readonly string[], id: string, max = 2): string[] {
  if (selected.includes(id)) {
    return selected.filter((item) => item !== id);
  }
  if (selected.length >= max) {
    return [...selected.slice(1), id];
  }
  return [...selected, id];
}

export function countBy(values: readonly string[]): CountBucket[] {
  const map = new Map<string, number>();
  for (const value of values) {
    const key = value || "unknown";
    map.set(key, (map.get(key) ?? 0) + 1);
  }
  return [...map.entries()]
    .map(([key, count]) => ({ key, count }))
    .sort((a, b) => b.count - a.count || a.key.localeCompare(b.key));
}

export function filterByText<T>(
  rows: readonly T[],
  query: string,
  getText: (row: T) => string,
): T[] {
  const needle = query.trim().toLowerCase();
  if (!needle) {
    return [...rows];
  }
  return rows.filter((row) => getText(row).toLowerCase().includes(needle));
}

export function sortBy<T>(
  rows: readonly T[],
  dir: SortDir,
  getValue: (row: T) => string | number | null | undefined,
): T[] {
  const sign = dir === "asc" ? 1 : -1;
  return [...rows].sort((a, b) => {
    const left = getValue(a);
    const right = getValue(b);
    if (left == null && right == null) {
      return 0;
    }
    if (left == null) {
      return 1;
    }
    if (right == null) {
      return -1;
    }
    if (typeof left === "number" && typeof right === "number") {
      return (left - right) * sign;
    }
    return String(left).localeCompare(String(right)) * sign;
  });
}
