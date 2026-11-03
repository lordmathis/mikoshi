import { Capacitor, registerPlugin } from "@capacitor/core";

export interface ServerConfigPlugin {
  getServerUrl(): Promise<{ url: string | null }>;
  setServerUrl(options: { url: string }): Promise<void>;
}

export const ServerConfig = registerPlugin<ServerConfigPlugin>("ServerConfig", {
  web: () => ({
    getServerUrl: () => Promise.resolve({ url: null }),
  }),
});

// Remote mode serves the SPA from the mikoshi origin, so a localhost
// hostname on the native platform means bundled (onboarding) mode.
export function needsOnboarding(): boolean {
  return Capacitor.isNativePlatform() && window.location.hostname === "localhost";
}
