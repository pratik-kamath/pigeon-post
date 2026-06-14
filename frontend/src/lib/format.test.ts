import { titleCaseCity, formatCountdown } from "./format";

test("titleCaseCity capitalizes each word", () => {
  expect(titleCaseCity("san francisco")).toBe("San Francisco");
  expect(titleCaseCity("tokyo")).toBe("Tokyo");
});

test("formatCountdown formats hours+minutes, minutes-only, sub-minute, and arrival", () => {
  expect(formatCountdown(2 * 3600_000 + 5 * 60_000)).toBe("2h 5m");
  expect(formatCountdown(5 * 60_000)).toBe("5m");
  expect(formatCountdown(30_000)).toBe("<1m");
  expect(formatCountdown(0)).toBe("arriving");
  expect(formatCountdown(-1000)).toBe("arriving");
});
