import { useEffect, useRef } from "react";

const GIS_SRC = "https://accounts.google.com/gsi/client";

interface GoogleId {
  initialize: (opts: { client_id: string; callback: (r: { credential: string }) => void }) => void;
  renderButton: (el: HTMLElement, opts: Record<string, unknown>) => void;
}
declare global {
  interface Window { google?: { accounts: { id: GoogleId } }; }
}

export function GoogleSignInButton({ onCredential }: { onCredential: (idToken: string) => void }) {
  const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID;
  const containerRef = useRef<HTMLDivElement>(null);
  const cbRef = useRef(onCredential);
  useEffect(() => { cbRef.current = onCredential; }, [onCredential]);

  useEffect(() => {
    if (!clientId) return;
    const el = containerRef.current;
    if (!el) return;

    function init() {
      const id = window.google?.accounts?.id;
      if (!id || !el) return;
      id.initialize({ client_id: clientId as string, callback: (r) => cbRef.current(r.credential) });
      el.replaceChildren(); // idempotent: avoid a doubled button under React StrictMode's double-invoke
      id.renderButton(el, { theme: "filled_black", size: "large", text: "continue_with" });
    }

    if (window.google?.accounts?.id) { init(); return; }
    const existing = document.querySelector<HTMLScriptElement>(`script[src="${GIS_SRC}"]`);
    if (existing) {
      existing.addEventListener("load", init);
      return () => existing.removeEventListener("load", init);
    }
    const s = document.createElement("script");
    s.src = GIS_SRC;
    s.async = true;
    s.defer = true;
    s.addEventListener("load", init);
    document.head.appendChild(s);
    return () => s.removeEventListener("load", init);
  }, [clientId]);

  if (!clientId) return null;
  return <div ref={containerRef} className="google-btn" />;
}
