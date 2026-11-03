// Structural subset of @capacitor/cli's CapacitorConfig — the CLI parses
// this file itself; the type just keeps the fields we set honest.
interface CapacitorConfig {
  appId: string;
  appName: string;
  webDir: string;
}

// The server URL is configured in-app (onboarding) and applied by
// MainActivity at runtime — never baked into this file.
const config: CapacitorConfig = {
  appId: 'app.mikoshi',
  appName: 'Mikoshi',
  webDir: 'dist',
};

export default config;
