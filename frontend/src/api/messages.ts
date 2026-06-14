import { apiFetch } from "./client";

export type MessageStatus = "in_flight" | "delivered" | "lost";

export interface Message {
  id: number;
  sender: string;
  recipient: string;
  body: string;
  origin: string;
  destination: string;
  distance_km: number;
  status: MessageStatus;
  sent_at: string;
  arrival_at: string;
  resolved_at: string | null;
}

export interface SendPayload {
  recipient: string;
  origin: string;
  destination: string;
  body: string;
}

export const listSent = () => apiFetch<Message[]>("/messages/sent");

export const sendMessage = (payload: SendPayload) =>
  apiFetch<Message>("/messages", { method: "POST", body: JSON.stringify(payload) });
