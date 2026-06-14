import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SendDialog } from "./SendDialog";
import * as messagesApi from "../api/messages";
import { ApiError } from "../api/client";
import type { City } from "../api/cities";

const cities: City[] = [
  { name: "new york", lat: 40.7, lon: -74 },
  { name: "tokyo", lat: 35.6, lon: 139.6 },
];

beforeEach(() => vi.restoreAllMocks());

function fill(recipient = "alex") {
  return (async () => {
    await userEvent.type(screen.getByLabelText(/recipient/i), recipient);
    await userEvent.selectOptions(screen.getByLabelText(/from/i), "new york");
    await userEvent.selectOptions(screen.getByLabelText(/to/i), "tokyo");
    await userEvent.type(screen.getByLabelText(/message/i), "wish you were here");
  })();
}

test("blocks same origin and destination", async () => {
  render(<SendDialog cities={cities} onClose={() => {}} onSent={() => {}} />);
  await userEvent.type(screen.getByLabelText(/recipient/i), "alex");
  await userEvent.selectOptions(screen.getByLabelText(/from/i), "tokyo");
  await userEvent.selectOptions(screen.getByLabelText(/to/i), "tokyo");
  await userEvent.type(screen.getByLabelText(/message/i), "hi");
  await userEvent.click(screen.getByRole("button", { name: /send/i }));
  expect(screen.getByText(/must differ/i)).toBeInTheDocument();
});

test("sends and reports the created message", async () => {
  const created = { id: 99 } as messagesApi.Message;
  const spy = vi.spyOn(messagesApi, "sendMessage").mockResolvedValue(created);
  const onSent = vi.fn();
  render(<SendDialog cities={cities} onClose={() => {}} onSent={onSent} />);
  await fill();
  await userEvent.click(screen.getByRole("button", { name: /send/i }));
  await waitFor(() => expect(onSent).toHaveBeenCalledWith(created));
  expect(spy).toHaveBeenCalledWith({ recipient: "alex", origin: "new york", destination: "tokyo", body: "wish you were here" });
});

test("surfaces an unknown-recipient 404", async () => {
  vi.spyOn(messagesApi, "sendMessage").mockRejectedValue(new ApiError(404, { detail: "recipient not found" }));
  render(<SendDialog cities={cities} onClose={() => {}} onSent={() => {}} />);
  await fill("ghost");
  await userEvent.click(screen.getByRole("button", { name: /send/i }));
  await waitFor(() => expect(screen.getByText(/recipient not found/i)).toBeInTheDocument());
});

test("blocks an empty recipient before calling the API", async () => {
  const spy = vi.spyOn(messagesApi, "sendMessage");
  render(<SendDialog cities={cities} onClose={() => {}} onSent={() => {}} />);
  await userEvent.selectOptions(screen.getByLabelText(/from/i), "new york");
  await userEvent.selectOptions(screen.getByLabelText(/to/i), "tokyo");
  await userEvent.type(screen.getByLabelText(/message/i), "hi");
  await userEvent.click(screen.getByRole("button", { name: /send/i }));
  expect(screen.getByText(/required/i)).toBeInTheDocument();
  expect(spy).not.toHaveBeenCalled();
});

test("a 422 with array detail shows a message without crashing", async () => {
  vi.spyOn(messagesApi, "sendMessage").mockRejectedValue(
    new ApiError(422, { detail: [{ loc: ["body", "body"], msg: "must not be blank", type: "value_error" }] })
  );
  render(<SendDialog cities={cities} onClose={() => {}} onSent={() => {}} />);
  await fill();
  await userEvent.click(screen.getByRole("button", { name: /send/i }));
  await waitFor(() => expect(screen.getByText(/must not be blank/i)).toBeInTheDocument());
});
