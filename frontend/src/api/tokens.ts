const ACCESS = "pp_access";
const REFRESH = "pp_refresh";

export const tokens = {
  get access() { return localStorage.getItem(ACCESS); },
  get refresh() { return localStorage.getItem(REFRESH); },
  set(pair: { access_token: string; refresh_token: string }) {
    localStorage.setItem(ACCESS, pair.access_token);
    localStorage.setItem(REFRESH, pair.refresh_token);
  },
  clear() {
    localStorage.removeItem(ACCESS);
    localStorage.removeItem(REFRESH);
  },
};
