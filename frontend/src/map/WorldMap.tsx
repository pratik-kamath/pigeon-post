import { useEffect, useMemo, useRef, useState } from "react";
import type { City } from "../api/cities";
import type { Message } from "../api/messages";
import { project } from "./projection";
import { pigeonPosition } from "./pigeon";
import { flightSegments } from "./flightSegments";
import { GRID_COLS, GRID_ROWS, isLand } from "./worldGrid";
import { CityMarker } from "../components/CityMarker";
import { PigeonSprite } from "../components/PigeonSprite";

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

  const tiles = useMemo(() => {
    const cells: { c: number; r: number }[] = [];
    for (let r = 0; r < GRID_ROWS; r++)
      for (let c = 0; c < GRID_COLS; c++) if (isLand(c, r)) cells.push({ c, r });
    return cells;
  }, []);

  return (
    <div className="pk-map scanlines" role="region" aria-label="World map of pigeons in flight">
      {tiles.map(({ c, r }) => (
        <span
          key={`${c}-${r}`}
          className="tile"
          style={{
            left: `${(c / GRID_COLS) * 100}%`,
            top: `${(r / GRID_ROWS) * 100}%`,
            width: `${100 / GRID_COLS}%`,
            height: `${100 / GRID_ROWS}%`,
          }}
        />
      ))}
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
        return <CityMarker key={city.name} name={city.name} xPct={p.x * 100} yPct={p.y * 100} />;
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
