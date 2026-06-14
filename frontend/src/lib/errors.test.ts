import { ApiError } from "../api/client";
import { errorMessage } from "./errors";

test("string detail is returned", () => {
  expect(errorMessage(new ApiError(404, { detail: "recipient not found" }), "fb")).toBe("recipient not found");
});

test("Pydantic array detail returns the first msg (never an object)", () => {
  const err = new ApiError(422, { detail: [{ loc: ["body", "recipient"], msg: "must not be blank", type: "value_error" }] });
  expect(errorMessage(err, "fb")).toBe("must not be blank");
});

test("anything else returns the fallback", () => {
  expect(errorMessage(new Error("boom"), "fb")).toBe("fb");
});
