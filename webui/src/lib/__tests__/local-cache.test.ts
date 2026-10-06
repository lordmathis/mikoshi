import { describe, it, expect, beforeEach } from "vitest";
import { localCache } from "../local-cache.ts";

describe("localCache", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("round-trips a value", () => {
    localCache.set("key", { a: 1, b: ["x"] });
    expect(localCache.get<{ a: number; b: string[] }>("key")).toEqual({
      a: 1,
      b: ["x"],
    });
  });

  it("returns null for missing keys", () => {
    expect(localCache.get("missing")).toBeNull();
  });

  it("returns null for corrupt JSON", () => {
    localStorage.setItem("corrupt", "{not json");
    expect(localCache.get("corrupt")).toBeNull();
  });

  it("refuses to write payloads over 512 KB", () => {
    localCache.set("big", "x".repeat(512 * 1024 + 1));
    expect(localStorage.getItem("big")).toBeNull();
  });

  it("writes payloads at the 512 KB boundary", () => {
    const value = "x".repeat(512 * 1024 - 3);
    localCache.set("big", value);
    expect(localStorage.getItem("big")).toContain(value);
  });

  it("remove deletes the key", () => {
    localCache.set("key", "value");
    localCache.remove("key");
    expect(localCache.get("key")).toBeNull();
  });
});
