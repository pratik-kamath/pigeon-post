import { parseServerUtc } from "./time";

test("treats a timezone-less server string as UTC", () => {
  const d = parseServerUtc("2026-06-14T10:00:00");
  expect(d.getTime()).toBe(Date.UTC(2026, 5, 14, 10, 0, 0));
});

test("respects an explicit Z", () => {
  const d = parseServerUtc("2026-06-14T10:00:00Z");
  expect(d.getTime()).toBe(Date.UTC(2026, 5, 14, 10, 0, 0));
});

test("respects fractional seconds without offset", () => {
  const d = parseServerUtc("2026-06-14T10:00:00.500000");
  expect(d.getTime()).toBe(Date.UTC(2026, 5, 14, 10, 0, 0, 500));
});

test("respects a positive UTC offset", () => {
  expect(parseServerUtc("2026-06-14T20:00:00+10:00").getTime()).toBe(
    Date.UTC(2026, 5, 14, 10, 0, 0)
  );
});

test("respects a negative UTC offset", () => {
  expect(parseServerUtc("2026-06-14T06:00:00-04:00").getTime()).toBe(
    Date.UTC(2026, 5, 14, 10, 0, 0)
  );
});
