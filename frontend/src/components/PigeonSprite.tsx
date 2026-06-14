import type { Message } from "../api/messages";

interface Props {
  message: Message;
  xPct: number;
  yPct: number;
  selected: boolean;
  onSelect: (id: number) => void;
}

export function PigeonSprite({ message, xPct, yPct, selected, onSelect }: Props) {
  const cls = [
    "pigeon",
    `pigeon--${message.status}`,
    selected ? "pigeon--selected" : "",
  ].join(" ").trim();
  return (
    <button
      type="button"
      className={cls}
      style={{ left: `${xPct}%`, top: `${yPct}%` }}
      onClick={() => onSelect(message.id)}
      aria-label={`Pigeon to ${message.recipient} (${message.status})`}
    >
      <span className="pigeon-wing" aria-hidden="true" />
    </button>
  );
}
