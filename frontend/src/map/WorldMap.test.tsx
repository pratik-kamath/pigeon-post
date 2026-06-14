import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { WorldMap } from "./WorldMap";
import type { City } from "../api/cities";
import type { Message } from "../api/messages";

const cities: City[] = [
  { name: "new york", lat: 40.7128, lon: -74.006 },
  { name: "tokyo", lat: 35.6762, lon: 139.6503 },
];
const messages: Message[] = [
  { id: 1, sender: "me", recipient: "alex", body: "hi", origin: "new york",
    destination: "tokyo", distance_km: 1, status: "in_flight",
    sent_at: "2026-06-14T00:00:00", arrival_at: "2999-01-01T00:00:00", resolved_at: null },
];

test("renders city markers, a sprite, and a dotted flight path", () => {
  const { container } = render(
    <WorldMap cities={cities} messages={messages} selectedId={null} onSelect={() => {}} />
  );
  expect(screen.getByText("New York")).toBeInTheDocument();
  expect(screen.getByText("Tokyo")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /pigeon to alex/i })).toBeInTheDocument();
  expect(container.querySelectorAll(".flight-paths line").length).toBeGreaterThan(0);
});

test("clicking a pigeon selects it", async () => {
  const onSelect = vi.fn();
  render(<WorldMap cities={cities} messages={messages} selectedId={null} onSelect={onSelect} />);
  await userEvent.click(screen.getByRole("button", { name: /pigeon to alex/i }));
  expect(onSelect).toHaveBeenCalledWith(1);
});

test("skips pigeons whose cities are unknown", () => {
  const bad = [{ ...messages[0], id: 2, origin: "atlantis" }];
  render(<WorldMap cities={cities} messages={bad} selectedId={null} onSelect={() => {}} />);
  expect(screen.queryByRole("button", { name: /pigeon to alex/i })).toBeNull();
});
