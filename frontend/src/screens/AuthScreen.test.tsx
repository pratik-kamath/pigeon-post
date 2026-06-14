import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuthScreen } from "./AuthScreen";
import * as useAuthMod from "../auth/useAuth";

function mockAuth(over: Partial<ReturnType<typeof useAuthMod.useAuth>> = {}) {
  vi.spyOn(useAuthMod, "useAuth").mockReturnValue({
    user: null, status: "anonymous",
    login: vi.fn().mockResolvedValue(undefined),
    register: vi.fn().mockResolvedValue(undefined),
    loginWithGoogle: vi.fn(), logout: vi.fn(),
    ...over,
  });
}

beforeEach(() => vi.restoreAllMocks()); // isolate the useAuth spy between tests

test("logs in with entered credentials", async () => {
  const login = vi.fn().mockResolvedValue(undefined);
  mockAuth({ login });
  render(<AuthScreen />);
  await userEvent.type(screen.getByLabelText(/email/i), "a@b.com");
  await userEvent.type(screen.getByLabelText(/password/i), "password123");
  await userEvent.click(screen.getByRole("button", { name: /log in/i }));
  expect(login).toHaveBeenCalledWith("a@b.com", "password123");
});

test("shows an error when login is rejected", async () => {
  mockAuth({ login: vi.fn().mockRejectedValue(new Error("nope")) });
  render(<AuthScreen />);
  await userEvent.type(screen.getByLabelText(/email/i), "a@b.com");
  await userEvent.type(screen.getByLabelText(/password/i), "x");
  await userEvent.click(screen.getByRole("button", { name: /log in/i }));
  await waitFor(() => expect(screen.getByText(/couldn't log in/i)).toBeInTheDocument());
});

test("can switch to register and submit username+email+password", async () => {
  const register = vi.fn().mockResolvedValue(undefined);
  mockAuth({ register });
  render(<AuthScreen />);
  await userEvent.click(screen.getByRole("button", { name: /create account/i }));
  await userEvent.type(screen.getByLabelText(/username/i), "pratik");
  await userEvent.type(screen.getByLabelText(/email/i), "a@b.com");
  await userEvent.type(screen.getByLabelText(/password/i), "password123");
  await userEvent.click(screen.getByRole("button", { name: /^register$/i }));
  expect(register).toHaveBeenCalledWith("pratik", "a@b.com", "password123");
});
