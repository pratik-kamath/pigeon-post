import { useEffect, useRef } from "react";

/** Run `fn` immediately and then every `intervalMs`. Always calls the latest
 *  `fn` without resetting the timer when it changes. */
export function usePolling(fn: () => void, intervalMs: number) {
  const saved = useRef(fn);
  // Update the ref in an effect, not during render (react-hooks/refs).
  useEffect(() => { saved.current = fn; }, [fn]);
  useEffect(() => {
    const run = () => saved.current();
    run();
    const id = setInterval(run, intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
}
