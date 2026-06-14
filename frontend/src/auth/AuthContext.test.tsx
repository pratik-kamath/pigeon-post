import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuthProvider, useAuth } from "./AuthContext";
import * as authApi from "../api/auth";

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
