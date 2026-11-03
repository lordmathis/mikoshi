import { useEffect, useState } from "react";
import { ServerConfig } from "./lib/native.ts";
import { Button } from "./ui/button.tsx";
import { Input } from "./ui/input.tsx";
import { Label } from "./ui/label.tsx";

export function OnboardingScreen() {
  const [url, setUrl] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    ServerConfig.getServerUrl().then(({ url }) => {
      if (url) setUrl(url);
    });
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = url.trim();
    if (!trimmed) {
      setError("Server URL is required");
      return;
    }
    setError(null);
    // The activity recreates underneath; this promise may never settle
    void ServerConfig.setServerUrl({ url: trimmed });
  };

  return (
    <div className="flex h-dvh items-center justify-center bg-cp-bg p-4">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-md space-y-6 border border-cp-border bg-cp-surface p-8 cp-cut-12"
      >
        <div className="space-y-2">
          <h1 className="text-lg font-bold uppercase tracking-[0.15em] text-primary">
            Mikoshi
          </h1>
          <p className="text-sm text-foreground/70">
            Enter your mikoshi server URL to connect.
          </p>
        </div>
        <div className="space-y-2">
          <Label htmlFor="server-url">Server URL</Label>
          <Input
            id="server-url"
            type="url"
            placeholder="https://mikoshi.home.example.com"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            autoFocus
          />
        </div>
        {error && <p className="text-sm text-cp-red">{error}</p>}
        <Button type="submit" className="w-full">
          Connect
        </Button>
      </form>
    </div>
  );
}
