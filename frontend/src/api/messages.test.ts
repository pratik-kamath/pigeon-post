import * as client from "./client";
import { listSent, sendMessage } from "./messages";

beforeEach(() => vi.restoreAllMocks());

test("listSent GETs /messages/sent", async () => {
  const spy = vi.spyOn(client, "apiFetch").mockResolvedValue([] as unknown as never);
  await listSent();
  expect(spy).toHaveBeenCalledWith("/messages/sent");
});

test("sendMessage POSTs the payload to /messages", async () => {
  const spy = vi.spyOn(client, "apiFetch").mockResolvedValue({ id: 1 } as unknown as never);
  await sendMessage({ recipient: "alex", origin: "new york", destination: "tokyo", body: "hi" });
  expect(spy).toHaveBeenCalledWith(
    "/messages",
    expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ recipient: "alex", origin: "new york", destination: "tokyo", body: "hi" }),
    })
  );
});
