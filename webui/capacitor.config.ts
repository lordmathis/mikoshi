import type { CapacitorConfig } from '@capacitor/cli';

// Domains come from the environment so they never land in the repo.
// Copy webui/.env.capacitor.example to webui/.env.capacitor (gitignored)
// or export the variables before running `npm run android:sync`.
const MIKOSHI_URL = process.env.MIKOSHI_URL;
const AUTHENLIA_DOMAIN = process.env.AUTHENLIA_DOMAIN;

if (!MIKOSHI_URL) {
  throw new Error(
    'MIKOSHI_URL is not set — copy webui/.env.capacitor.example to ' +
      'webui/.env.capacitor and fill in your domains before syncing the app.'
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
    allowNavigation: AUTHENLIA_DOMAIN ? [AUTHENLIA_DOMAIN] : [],
  },
};

export default config;
