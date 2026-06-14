import { ApiError } from "../api/client";

/** A user-facing string from a thrown API error. FastAPI/Pydantic 422s put an
 *  ARRAY of objects in `detail`; route errors put a string. Never returns a
 *  non-string (rendering one would crash React). */
export function errorMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiError && err.body && typeof err.body === "object") {
    const detail = (err.body as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      const first = detail[0] as { msg?: unknown } | undefined;
      if (first && typeof first.msg === "string") return first.msg;
    }
  }
  return fallback;
}
