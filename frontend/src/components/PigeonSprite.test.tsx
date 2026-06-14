import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PigeonSprite } from "./PigeonSprite";
import type { Message } from "../api/messages";

const base: Message = {
  id: 7, sender: "me", recipient: "alex", body: "hi", origin: "new york",
  destination: "tokyo", distance_km: 1, status: "in_flight",
  sent_at: "2026-06-14T00:00:00", arrival_at: "2026-06-14T10:00:00", resolved_at: null,
};

test("renders at the given position and fires onSelect", async () => {
  const onSelect = vi.fn();
  render(<PigeonSprite message={base} xPct={50} yPct={25} selected={false} onSelect={onSelect} />);
  const btn = screen.getByRole("button", { name: /pigeon to alex/i });
  expect(btn).toHaveStyle({ left: "50%", top: "25%" });
  await userEvent.click(btn);
  expect(onSelect).toHaveBeenCalledWith(7);
});

test("lost pigeons get the lost modifier class", () => {
  render(<PigeonSprite message={{ ...base, status: "lost" }} xPct={10} yPct={10} selected={false} onSelect={() => {}} />);
  expect(screen.getByRole("button", { name: /pigeon to alex/i }).className).toMatch(/pigeon--lost/);
});
