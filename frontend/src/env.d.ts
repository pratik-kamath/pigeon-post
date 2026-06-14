/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_GOOGLE_CLIENT_ID?: string;
}
interface ImportMeta {
  readonly env: ImportMetaEnv;
}

declare module "@fontsource/press-start-2p";
declare module "@fontsource/vt323";
