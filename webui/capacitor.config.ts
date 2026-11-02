// Structural subset of @capacitor/cli's CapacitorConfig — the CLI parses
// this file itself; the type just keeps the fields we set honest.
interface CapacitorConfig {
  appId: string;
  appName: string;
  webDir: string;
  server?: {
    url?: string;
    allowNavigation?: string[];
  };
}

const MIKOSHI_URL = process.env.MIKOSHI_URL;
const AUTHELIA_DOMAIN = process.env.AUTHELIA_DOMAIN;

if (!MIKOSHI_URL) {
  throw new Error(
    'MIKOSHI_URL is not set!'
  );
}

const config: CapacitorConfig = {
  appId: 'app.mikoshi',
  appName: 'Mikoshi',
  webDir: 'dist',
  server: {
    url: MIKOSHI_URL,
    // The Authelia portal lives on another origin; without this the
    // forward-auth login redirect is blocked by the WebView.
    allowNavigation: AUTHELIA_DOMAIN ? [AUTHELIA_DOMAIN] : [],
  },
};

export default config;
