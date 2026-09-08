export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "Never";
  return new Date(iso).toLocaleString();
}

export function formatTimestamp(iso: string | null | undefined): string {
  if (!iso) return "—";
  return iso.slice(0, 19).replace("T", " ");
}

export function formatMb(mb: number | null | undefined): string {
  if (mb === null || mb === undefined) return "—";
  return `${(mb / 1024).toFixed(1)} GB`;
}

export function formatSeconds(seconds: number | null | undefined, decimals = 1): string {
  if (seconds === null || seconds === undefined) return "—";
  return seconds.toFixed(decimals);
}

export function pluralize(count: number, singular: string, plural = `${singular}s`): string {
  return count === 1 ? singular : plural;
}
