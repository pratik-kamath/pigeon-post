import { titleCaseCity } from "../lib/format";

export function CityMarker({ name, xPct, yPct }: { name: string; xPct: number; yPct: number }) {
  return (
    <div className="city" style={{ left: `${xPct}%`, top: `${yPct}%` }}>
      <span className="city-dot" />
      <span className="city-label">{titleCaseCity(name)}</span>
    </div>
  );
}
