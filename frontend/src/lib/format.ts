export function titleCaseCity(name: string): string {
  return name.replace(/\b\w/g, (c) => c.toUpperCase());
}

export function formatCountdown(ms: number): string {
  if (ms <= 0) return "arriving";
  if (ms < 60_000) return "<1m";
  const totalMin = Math.floor(ms / 60_000);
  const h = Math.floor(totalMin / 60);
  const m = totalMin % 60;
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}
