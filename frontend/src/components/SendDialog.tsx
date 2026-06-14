import { useState, type FormEvent } from "react";
import type { City } from "../api/cities";
import { sendMessage, type Message } from "../api/messages";
import { errorMessage } from "../lib/errors";
import { titleCaseCity } from "../lib/format";
import { PixelButton } from "./PixelButton";

interface Props {
  cities: City[];
  onClose: () => void;
  onSent: (m: Message) => void;
}

export function SendDialog({ cities, onClose, onSent }: Props) {
  const [recipient, setRecipient] = useState("");
  const [origin, setOrigin] = useState("");
  const [destination, setDestination] = useState("");
  const [body, setBody] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!recipient.trim() || !body.trim()) {
      setError("Recipient and message are required.");
      return;
    }
    if (!origin || !destination || origin === destination) {
      setError("Origin and destination must differ.");
      return;
    }
    setBusy(true);
    try {
      const msg = await sendMessage({ recipient: recipient.trim(), origin, destination, body });
      onSent(msg);
      onClose();
    } catch (err) {
      // errorMessage safely stringifies even a Pydantic array `detail`.
      setError(errorMessage(err, "Couldn't send the pigeon. Try again."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <form className="pk-box send-dialog" onClick={(e) => e.stopPropagation()} onSubmit={onSubmit}>
        <h2 className="send-title">SEND A PIGEON</h2>
        <label>Recipient
          <input value={recipient} onChange={(e) => setRecipient(e.target.value)} />
        </label>
        <label>From
          <select value={origin} onChange={(e) => setOrigin(e.target.value)}>
            <option value="">—</option>
            {cities.map((c) => <option key={c.name} value={c.name}>{titleCaseCity(c.name)}</option>)}
          </select>
        </label>
        <label>To
          <select value={destination} onChange={(e) => setDestination(e.target.value)}>
            <option value="">—</option>
            {cities.map((c) => <option key={c.name} value={c.name}>{titleCaseCity(c.name)}</option>)}
          </select>
        </label>
        <label>Message
          <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={3} />
        </label>
        {error && <p className="auth-error" role="alert">{error}</p>}
        <div className="send-actions">
          <PixelButton type="submit" disabled={busy}>SEND</PixelButton>
          <button type="button" className="auth-toggle" onClick={onClose}>Cancel</button>
        </div>
      </form>
    </div>
  );
}
