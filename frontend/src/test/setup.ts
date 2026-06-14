import "@testing-library/jest-dom/vitest";

if (!globalThis.requestAnimationFrame) {
  globalThis.requestAnimationFrame = ((cb: FrameRequestCallback) =>
    setTimeout(() => cb(Date.now()), 16) as unknown as number) as typeof requestAnimationFrame;
  globalThis.cancelAnimationFrame = ((id: number) =>
    clearTimeout(id as unknown as ReturnType<typeof setTimeout>)) as typeof cancelAnimationFrame;
}

// Node 25 ships a native but incomplete `localStorage` global (no `.clear()`).
// Vitest's jsdom environment intentionally skips overriding keys that already
// exist in the Node global unless they're in its explicit allow-list, so
// `localStorage` ends up as the broken Node 25 stub rather than jsdom's full
// implementation.  Fix it here where `globalThis.jsdom` is already set.
if (typeof (globalThis as Record<string, unknown>)["jsdom"] !== "undefined") {
  const jsdomWindow = ((globalThis as Record<string, unknown>)["jsdom"] as { window: Window }).window;
  const { localStorage, sessionStorage } = jsdomWindow;
  Object.defineProperty(globalThis, "localStorage", {
    value: localStorage,
    configurable: true,
    writable: true,
  });
  Object.defineProperty(globalThis, "sessionStorage", {
    value: sessionStorage,
    configurable: true,
    writable: true,
  });
}
