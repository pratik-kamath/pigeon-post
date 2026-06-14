import { useEffect, useRef, useState } from "react";
import { useAuth } from "../auth/useAuth";
import { fetchCities, type City } from "../api/cities";
import { listSent, type Message } from "../api/messages";
import { mergeServer, withOptimistic } from "../lib/sentStore";
import { usePolling } from "../lib/usePolling";
import { WorldMap } from "../map/WorldMap";
import { DialogueBox } from "../components/DialogueBox";
import { SendDialog } from "../components/SendDialog";
import { PixelButton } from "../components/PixelButton";
import { titleCaseCity, formatCountdown } from "../lib/format";
import { parseServerUtc } from "../lib/time";
import { useClock } from "../lib/useClock";

function statusLine(m: Message, now: number): string {
  const to = `#${m.id} → ${m.recipient} @ ${titleCaseCity(m.destination)}`;
  if (m.status === "delivered") return `${to} · delivered ✓`;
  if (m.status === "lost") return `${to} · lost ✗`;
  const left = parseServerUtc(m.arrival_at).getTime() - now;
  return `${to} · ${formatCountdown(left)} to arrival`;
}

export function Dashboard() {
  const { user, logout } = useAuth();
  const now = useClock(15_000);
  const [cities, setCities] = useState<City[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [sendOpen, setSendOpen] = useState(false);
  // Optimistic sends not yet returned by a poll (see sentStore): a poll that
  // started before a send can't make the new pigeon vanish.
  const pendingRef = useRef<Message[]>([]);

  function applyPoll(server: Message[]) {
    const { pending, all } = mergeServer(pendingRef.current, server);
    pendingRef.current = pending;
    setMessages(all);
  }
  function addOptimistic(m: Message) {
    pendingRef.current = withOptimistic(pendingRef.current, m);
    setMessages((prev) => withOptimistic(prev, m));
  }

  useEffect(() => { fetchCities().then(setCities).catch(() => {}); }, []);
  usePolling(() => { listSent().then(applyPoll).catch(() => {}); }, 10_000);

  const selected = messages.find((m) => m.id === selectedId) ?? null;

  return (
    <div className="dashboard">
      <div className="pk-screen dashboard-screen scanlines boot">
        <div className="dash-bar">
          <span className="dash-title">PIGEON POST</span>
          <span className="dash-user">{user?.username}</span>
          <PixelButton onClick={() => setSendOpen(true)}>SEND</PixelButton>
          <button type="button" className="auth-toggle dash-logout" onClick={logout}>log out</button>
        </div>
        <WorldMap cities={cities} messages={messages} selectedId={selectedId} onSelect={setSelectedId} />
        <DialogueBox>
          {selected ? statusLine(selected, now)
            : messages.length === 0 ? "No pigeons aloft. Press SEND to launch one!"
            : "▸ Tap a pigeon to track it."}
        </DialogueBox>
      </div>
      {sendOpen && (
        <SendDialog
          cities={cities}
          onClose={() => setSendOpen(false)}
          onSent={addOptimistic}
        />
      )}
    </div>
  );
}
