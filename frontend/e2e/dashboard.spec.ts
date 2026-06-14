import { test, expect } from "@playwright/test";

const user = { id: 1, username: "pratik", email: "p@x.com", created_at: "2026-06-14T00:00:00" };
const cities = [
  { name: "new york", lat: 40.7128, lon: -74.006 },
  { name: "tokyo", lat: 35.6762, lon: 139.6503 },
];
const sent = [{
  id: 1, sender: "pratik", recipient: "alex", body: "hi", origin: "new york",
  destination: "tokyo", distance_km: 6700, status: "in_flight",
  sent_at: "2026-06-14T00:00:00", arrival_at: "2999-01-01T00:00:00", resolved_at: null,
}];

test.beforeEach(async ({ page }) => {
  // Seed a session and mock the API by path (works regardless of API base URL).
  await page.addInitScript(() => {
    localStorage.setItem("pp_access", "test-access");
    localStorage.setItem("pp_refresh", "test-refresh");
  });
  const json = (body: unknown) => ({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  await page.route("**/auth/me", (r) => r.fulfill(json(user)));
  await page.route("**/cities", (r) => r.fulfill(json(cities)));
  await page.route("**/messages/sent", (r) => r.fulfill(json(sent)));
});

test("dashboard shows the map, a pigeon, and opens the send dialog", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("region", { name: /world map/i })).toBeVisible();
  await expect(page.getByRole("button", { name: /pigeon to alex/i })).toBeVisible();
  await page.getByRole("button", { name: /^send$/i }).click();
  await expect(page.getByText(/send a pigeon/i)).toBeVisible();
});
