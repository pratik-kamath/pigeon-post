import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Dashboard } from "./Dashboard";
import * as citiesApi from "../api/cities";
import * as messagesApi from "../api/messages";
import * as useAuthMod from "../auth/useAuth";

const cities = [
  { name: "new york", lat: 40.7128, lon: -74.006 },
  { name: "tokyo", lat: 35.6762, lon: 139.6503 },
];
const sent = [{
  id: 1, sender: "me", recipient: "alex", body: "hi", origin: "new york",
  destination: "tokyo", distance_km: 1, status: "in_flight" as const,
  sent_at: "2026-06-14T00:00:00", arrival_at: "2999-01-01T00:00:00", resolved_at: null,
}];

beforeEach(() => {
  vi.restoreAllMocks();
  vi.spyOn(citiesApi, "fetchCities").mockResolvedValue(cities);
  vi.spyOn(messagesApi, "listSent").mockResolvedValue(sent);
  vi.spyOn(useAuthMod, "useAuth").mockReturnValue({
    user: { id: 1, username: "pratik", email: "p@x.com", created_at: "2026-01-01T00:00:00" },
    status: "authenticated", login: vi.fn(), register: vi.fn(),
    loginWithGoogle: vi.fn(), logout: vi.fn(),
  });
});

test("loads cities + sent pigeons and shows a sprite", async () => {
  render(<Dashboard />);
  await waitFor(() => expect(screen.getByRole("button", { name: /pigeon to alex/i })).toBeInTheDocument());
});

test("selecting a pigeon shows its status in the dialogue box", async () => {
  render(<Dashboard />);
  const sprite = await screen.findByRole("button", { name: /pigeon to alex/i });
  await userEvent.click(sprite);
  expect(screen.getByRole("status")).toHaveTextContent(/alex/i);
  expect(screen.getByRole("status")).toHaveTextContent(/tokyo/i);
});

test("SEND opens the dialog", async () => {
  render(<Dashboard />);
  await screen.findByRole("button", { name: /pigeon to alex/i });
  await userEvent.click(screen.getByRole("button", { name: /^send$/i }));
  expect(screen.getByText(/send a pigeon/i)).toBeInTheDocument();
});
