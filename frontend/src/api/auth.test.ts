import * as client from "./client";
import { login } from "./auth";
import { tokens } from "./tokens";

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

test("login stores the token pair then loads me()", async () => {
  const apiSpy = vi.spyOn(client, "apiFetch").mockImplementation(
    async (path: string) => {
      if (path === "/auth/login") {
        return { access_token: "a", refresh_token: "r" } as unknown;
      }
      if (path === "/auth/me") {
        return {
          id: 1, username: "pratik", email: "p@x.com",
          created_at: "2026-01-01T00:00:00",
        } as unknown;
      }
      throw new Error("unexpected path " + path);
    }
  );
  const user = await login("p@x.com", "pw");
  expect(tokens.access).toBe("a");
  expect((user as { username: string }).username).toBe("pratik");
  expect(apiSpy).toHaveBeenCalledWith(
    "/auth/login",
    expect.objectContaining({ method: "POST" })
  );
});
