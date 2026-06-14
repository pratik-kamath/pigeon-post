import { render } from "@testing-library/react";
import { GoogleSignInButton } from "./GoogleSignInButton";

interface MockId {
  initialize: (opts: { client_id: string; callback: (r: { credential: string }) => void }) => void;
  renderButton: (el: HTMLElement, opts: Record<string, unknown>) => void;
}
declare global {
  var google: { accounts: { id: MockId } } | undefined;
}

afterEach(() => {
  globalThis.google = undefined;
  vi.unstubAllEnvs();
});

test("renders nothing when no client id is configured", () => {
  vi.stubEnv("VITE_GOOGLE_CLIENT_ID", "");
  const { container } = render(<GoogleSignInButton onCredential={() => {}} />);
  expect(container.firstChild).toBeNull();
});

test("initializes GIS and forwards the credential", () => {
  vi.stubEnv("VITE_GOOGLE_CLIENT_ID", "client-123");
  let captured: ((r: { credential: string }) => void) | null = null;
  globalThis.google = {
    accounts: { id: {
      initialize: (opts) => { captured = opts.callback; },
      renderButton: vi.fn(),
    } },
  };
  const onCredential = vi.fn();
  render(<GoogleSignInButton onCredential={onCredential} />);
  expect(typeof captured).toBe("function");
  captured!({ credential: "id-token-xyz" });
  expect(onCredential).toHaveBeenCalledWith("id-token-xyz");
});
