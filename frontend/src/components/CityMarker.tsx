import { titleCaseCity } from "../lib/format";

export type LabelPlacement = "right" | "left" | "top" | "bottom";

export function CityMarker({
  name,
  xPct,
  yPct,
  placement = "right",
}: {
  name: string;
  xPct: number;
  yPct: number;
  placement?: LabelPlacement;
}) {
  return (
    <div className="city" style={{ left: `${xPct}%`, top: `${yPct}%` }}>
      <span className="city-dot" />
      <span className={`city-label city-label--${placement}`}>{titleCaseCity(name)}</span>
    </div>
  );
}
