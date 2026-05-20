import { describe, it, expect, vi } from "vitest";
import { matchesPatterns, fetchAllFilePaths } from "../connector-utils";
import { api } from "../api";

vi.mock("../api", () => ({
  api: {
    browseConnectorTree: vi.fn(),
  },
}));

const mockBrowse = vi.mocked(api.browseConnectorTree);

describe("matchesPatterns", () => {
  it("returns false for empty pattern string", () => {
    expect(matchesPatterns("foo.ts", "")).toBe(false);
  });

  it("matches exact filename", () => {
    expect(matchesPatterns("src/foo.ts", "foo.ts")).toBe(true);
  });

  it("matches exact full path", () => {
    expect(matchesPatterns("a/b/c.txt", "a/b/c.txt")).toBe(true);
  });

  it("matches wildcard *.ts against filename", () => {
    expect(matchesPatterns("src/test.ts", "*.ts")).toBe(true);
  });

  it("matches from comma-separated patterns", () => {
    expect(matchesPatterns("a.ts", "*.js, *.ts")).toBe(true);
  });

  it("does not crash on special regex chars in pattern", () => {
    expect(() => matchesPatterns("file[1].ts", "file[1].ts")).not.toThrow();
  });

  it("matches filename (last path segment) via wildcard", () => {
    expect(matchesPatterns("a/b/c.txt", "c.*")).toBe(true);
  });

  it("returns false when nothing matches", () => {
    expect(matchesPatterns("readme.md", "*.ts, *.js")).toBe(false);
  });
});

describe("fetchAllFilePaths", () => {
  it("returns single path for a file node", async () => {
    mockBrowse.mockResolvedValue({ path: "a.txt", name: "a.txt", type: "file" });

    const result = await fetchAllFilePaths("conn", "res", "a.txt");

    expect(result).toEqual(["a.txt"]);
  });

  it("collects files from a flat directory", async () => {
    mockBrowse.mockResolvedValue({
      path: "src",
      name: "src",
      type: "dir",
      children: [
        { path: "src/a.ts", name: "a.ts", type: "file" },
        { path: "src/b.ts", name: "b.ts", type: "file" },
      ],
    });

    const result = await fetchAllFilePaths("conn", "res", "src");

    expect(result).toEqual(["src/a.ts", "src/b.ts"]);
  });

  it("recurses into nested directories", async () => {
    mockBrowse
      .mockResolvedValueOnce({
        path: "",
        name: "root",
        type: "dir",
        children: [
          { path: "readme.md", name: "readme.md", type: "file" },
          { path: "src", name: "src", type: "dir" },
        ],
      })
      .mockResolvedValueOnce({
        path: "src",
        name: "src",
        type: "dir",
        children: [{ path: "src/index.ts", name: "index.ts", type: "file" }],
      });

    const result = await fetchAllFilePaths("conn", "res");

    expect(result).toEqual(["readme.md", "src/index.ts"]);
  });

  it("returns empty array when browseConnectorTree throws", async () => {
    mockBrowse.mockRejectedValue(new Error("network error"));

    const result = await fetchAllFilePaths("conn", "res", "missing");

    expect(result).toEqual([]);
  });
});
