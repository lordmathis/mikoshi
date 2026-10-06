const MAX_CACHE_BYTES = 512 * 1024;

export const localCache = {
  get<T>(key: string): T | null {
    try {
      const raw = localStorage.getItem(key);
      return raw === null ? null : (JSON.parse(raw) as T);
    } catch {
      return null;
    }
  },

  set(key: string, value: unknown): void {
    try {
      const serialized = JSON.stringify(value);
      if (serialized.length > MAX_CACHE_BYTES) return;
      localStorage.setItem(key, serialized);
    } catch {
      // Corrupt storage or quota exceeded — the cache is best-effort.
    }
  },

  remove(key: string): void {
    try {
      localStorage.removeItem(key);
    } catch {
      // Storage unavailable — best-effort.
    }
  },
};
