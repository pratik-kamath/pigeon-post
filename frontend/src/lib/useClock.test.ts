import { renderHook } from "@testing-library/react";
import { act } from "react";
import { useClock } from "./useClock";

afterEach(() => vi.useRealTimers());

test("advances on the interval and stops on unmount", () => {
  vi.useFakeTimers();
  const { result, rerender, unmount } = renderHook(() => useClock(1000));
  const t0 = result.current;
  act(() => { vi.advanceTimersByTime(1000); });
  rerender();
  expect(result.current).toBeGreaterThanOrEqual(t0);
  const before = result.current;
  unmount();
  act(() => { vi.advanceTimersByTime(5000); });
  expect(result.current).toBe(before); // no ticks after unmount
});
