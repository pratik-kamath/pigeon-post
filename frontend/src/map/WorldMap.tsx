import { useEffect, useMemo, useRef, useState } from "react";
import type { City } from "../api/cities";
import type { Message } from "../api/messages";
import { project } from "./projection";
import { pigeonPosition } from "./pigeon";
import { flightSegments } from "./flightSegments";
import { GRID_COLS, GRID_ROWS, isLand } from "./worldGrid";
import { CityMarker, type LabelPlacement } from "../components/CityMarker";
import { PigeonSprite } from "../components/PigeonSprite";

// Per-city label directions to keep dense clusters (W. Europe, US coasts,
// SE Australia) and right-edge cities (Tokyo, Sydney) from overlapping.
// Unlisted cities default to "right".
const LABEL_PLACEMENT: Record<string, LabelPlacement> = {
  london: "left",
  amsterdam: "top",
  paris: "bottom",
  cairo: "bottom",
  chicago: "left",
  "san francisco": "left",
  "los angeles": "bottom",
  dubai: "top",
  tokyo: "left",
  sydney: "left",
  melbourne: "bottom",
};

interface Props {
  cities: City[];
  messages: Message[];
  selectedId: number | null;
  onSelect: (id: number) => void;
}

export function WorldMap({ cities, messages, selectedId, onSelect }: Props) {
  const [now, setNow] = useState(() => Date.now());

  // Animate in-flight pigeons by advancing `now` each frame.
  const hasInFlight = messages.some((m) => m.status === "in_flight");
  const raf = useRef(0);
  useEffect(() => {
    if (!hasInFlight) return;
    const tick = () => { setNow(Date.now()); raf.current = requestAnimationFrame(tick); };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [hasInFlight]);

  const cityByName = useMemo(() => new Map(cities.map((c) => [c.name, c])), [cities]);

  // Land drawn once as run-length <rect>s in an SVG (crisp via crispEdges,
  // seam-free, far fewer nodes than per-cell tiles). Memoized so the dense grid
  // never re-renders on animation frames.
  const landRects = useMemo(() => {
    const rects = [];
    for (let r = 0; r < GRID_ROWS; r++) {
      let c = 0;
      while (c < GRID_COLS) {
        if (!isLand(c, r)) { c++; continue; }
        const start = c;
        while (c < GRID_COLS && isLand(c, r)) c++;
        rects.push(<rect key={`${r}-${start}`} x={start} y={r} width={c - start} height={1} />);
      }
    }
    return rects;
  }, []);

  return (
    <div className="pk-map scanlines" role="region" aria-label="World map of pigeons in flight">
      <svg
        className="land"
        viewBox={`0 0 ${GRID_COLS} ${GRID_ROWS}`}
        preserveAspectRatio="none"
        shapeRendering="crispEdges"
        aria-hidden="true"
      >
        {landRects}
      </svg>
      <svg className="flight-paths" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        {messages.flatMap((m) => {
          if (m.status !== "in_flight") return [];
          const o = cityByName.get(m.origin);
          const d = cityByName.get(m.destination);
          if (!o || !d) return [];
          return flightSegments(project(o.lat, o.lon), project(d.lat, d.lon)).map((s, i) => (
            <line
              key={`${m.id}-${i}`}
              x1={s.x1 * 100} y1={s.y1 * 100} x2={s.x2 * 100} y2={s.y2 * 100}
              stroke="var(--paper)" strokeWidth={0.5} strokeDasharray="1.5 1.5"
            />
          ));
        })}
      </svg>
      {cities.map((city) => {
        const p = project(city.lat, city.lon);
        return (
          <CityMarker
            key={city.name}
            name={city.name}
            xPct={p.x * 100}
            yPct={p.y * 100}
            placement={LABEL_PLACEMENT[city.name] ?? "right"}
          />
        );
      })}
      {messages.map((m) => {
        const p = pigeonPosition(m, cityByName, now);
        if (!p) return null;
        return (
          <PigeonSprite
            key={m.id}
            message={m}
            xPct={p.x * 100}
            yPct={p.y * 100}
            selected={m.id === selectedId}
            onSelect={onSelect}
          />
        );
      })}
    </div>
  );
}
