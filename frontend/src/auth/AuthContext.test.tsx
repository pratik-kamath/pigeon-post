import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuthProvider } from "./AuthContext";
import { useAuth } from "./useAuth";
import * as authApi from "../api/auth";
import type { User } from "../api/auth";
import { tokens } from "../api/tokens";

function Harness() {
  const { user, status, login } = useAuth();
  return (
    <div>
      <span>status:{status}</span>
      <span>user:{user?.username ?? "none"}</span>
      <button onClick={() => login("a@b.com", "pw")}>login</button>
    </div>
  );
}

beforeEach(() => localStorage.clear());

test("starts logged out and logs in", async () => {
  vi.spyOn(authApi, "me").mockRejectedValue(new Error("401")); // no session on boot
  vi.spyOn(authApi, "login").mockResolvedValue({
    id: 1, username: "pratik", email: "a@b.com", created_at: "2026-06-14T00:00:00",
  });
  render(<AuthProvider><Harness /></AuthProvider>);
  await waitFor(() => expect(screen.getByText("status:anonymous")).toBeInTheDocument());
  await userEvent.click(screen.getByText("login"));
  await waitFor(() => expect(screen.getByText("user:pratik")).toBeInTheDocument());
});

test("a me() that resolves after unmount does not throw", async () => {
  tokens.set({ access_token: "x", refresh_token: "y" });
  let resolveMe!: (u: User) => void;
  vi.spyOn(authApi, "me").mockReturnValue(
    new Promise<User>((r) => { resolveMe = r; })
  );
  const { unmount } = render(<AuthProvider><Harness /></AuthProvider>);
  unmount();
  resolveMe({ id: 1, username: "ghost", email: "g@x.com", created_at: "2026-01-01T00:00:00" });
  await Promise.resolve();
  // No throw / no act-on-unmounted error means the active-guard worked.
});
