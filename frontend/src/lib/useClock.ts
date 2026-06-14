import { useEffect, useState } from "react";

/** A coarse clock that re-renders consumers every `intervalMs`, so derived
 *  text like countdowns stays live between data polls. */
export function useClock(intervalMs: number): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
  return now;
}
