/** Parse a backend datetime. The backend emits naive UTC (no offset); JS would
 *  otherwise read such a string as local time, so we append `Z` when there's
 *  no timezone designator. */
export function parseServerUtc(s: string): Date {
  const hasTz = /[zZ]$|[+-]\d\d:?\d\d$/.test(s);
  return new Date(hasTz ? s : s + "Z");
}
