import { render, screen, waitFor } from "@testing-library/react";
import App from "./App";
import * as authApi from "./api/auth";
import { tokens } from "./api/tokens";

beforeEach(() => localStorage.clear());

test("a stale/invalid session falls back to the logged-out shell", async () => {
  tokens.set({ access_token: "stale", refresh_token: "ref" });
  const meSpy = vi.spyOn(authApi, "me").mockRejectedValue(new Error("401"));
  render(<App />);
  await waitFor(() =>
    expect(screen.getByText(/please log in/i)).toBeInTheDocument()
  );
  expect(meSpy).toHaveBeenCalled(); // the failed-session path was exercised
});
