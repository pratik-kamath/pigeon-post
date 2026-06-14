import { renderHook } from "@testing-library/react";
import { usePolling } from "./usePolling";

afterEach(() => vi.useRealTimers()); // restore even if an assertion above throws

test("calls immediately, then on each interval, and stops on unmount", () => {
  vi.useFakeTimers();
  const fn = vi.fn();
  const { unmount } = renderHook(() => usePolling(fn, 1000));
  expect(fn).toHaveBeenCalledTimes(1);      // immediate
  vi.advanceTimersByTime(2500);
  expect(fn).toHaveBeenCalledTimes(3);      // +2 ticks
  unmount();
  vi.advanceTimersByTime(5000);
  expect(fn).toHaveBeenCalledTimes(3);      // stopped
});

test("uses the latest fn without resetting the interval", () => {
  vi.useFakeTimers();
  const first = vi.fn();
  const second = vi.fn();
  const { rerender } = renderHook(({ fn }) => usePolling(fn, 1000), {
    initialProps: { fn: first },
  });
  expect(first).toHaveBeenCalledTimes(1);
  rerender({ fn: second });           // swapping fn must NOT restart the interval
  vi.advanceTimersByTime(1000);
  expect(second).toHaveBeenCalledTimes(1);
  expect(first).toHaveBeenCalledTimes(1); // old fn no longer called
});
