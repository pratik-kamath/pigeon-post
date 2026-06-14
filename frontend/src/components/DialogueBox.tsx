import type { ReactNode } from "react";

export function DialogueBox({ children }: { children: ReactNode }) {
  return (
    <div className="pk-box" role="status" aria-live="polite">
      {children}
    </div>
  );
}
