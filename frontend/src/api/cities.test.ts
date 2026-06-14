import * as client from "./client";
import { fetchCities } from "./cities";

test("fetchCities GETs /cities", async () => {
  const spy = vi.spyOn(client, "apiFetch").mockResolvedValue([] as unknown as never);
  await fetchCities();
  expect(spy).toHaveBeenCalledWith("/cities");
});
