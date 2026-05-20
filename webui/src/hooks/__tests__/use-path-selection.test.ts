import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { usePathSelection } from "../use-path-selection";
import type { FileNode } from "../../lib/api";

const tree: FileNode = {
  path: "",
  name: "root",
  type: "dir",
  children: [
    {
      path: "src",
      name: "src",
      type: "dir",
      children: [
        { path: "src/index.ts", name: "index.ts", type: "file" },
        { path: "src/utils.ts", name: "utils.ts", type: "file" },
      ],
    },
    { path: "readme.md", name: "readme.md", type: "file" },
  ],
};

function renderSelection(initialPaths: string[] = [], initialExcludePaths: string[] = []) {
  return renderHook(() => usePathSelection(initialPaths, initialExcludePaths));
}

function getPaths(result: ReturnType<typeof renderSelection>["result"]) {
  return result.current.selectedPaths;
}

describe("usePathSelection", () => {
  describe("isPathSelected", () => {
    it("returns false for empty path when root not in set", () => {
      const { result } = renderSelection();
      expect(result.current.isPathSelected("")).toBe(false);
    });

    it("returns true for empty path when root is explicitly in set", () => {
      const { result } = renderSelection([""]);
      expect(result.current.isPathSelected("")).toBe(true);
    });

    it("returns true when path is explicitly in set", () => {
      const { result } = renderSelection(["src/index.ts"]);
      expect(result.current.isPathSelected("src/index.ts")).toBe(true);
    });

    it("returns true when parent is selected (hierarchical inheritance)", () => {
      const { result } = renderSelection(["src"]);
      expect(result.current.isPathSelected("src/index.ts")).toBe(true);
    });

    it("returns false when path and no parent is selected", () => {
      const { result } = renderSelection();
      expect(result.current.isPathSelected("src/index.ts")).toBe(false);
    });
  });

  describe("toggleSelect", () => {
    it("adds an unselected path", () => {
      const { result } = renderSelection();
      act(() => result.current.toggleSelect("src", false, null));
      expect(getPaths(result).has("src")).toBe(true);
    });

    it("removes an explicitly selected path", () => {
      const { result } = renderSelection(["src"]);
      act(() => result.current.toggleSelect("src", false, null));
      expect(getPaths(result).has("src")).toBe(false);
    });

    it("excludes implicitly-selected child (parent selected, child toggled off)", () => {
      const { result } = renderSelection(["src"]);
      act(() => result.current.toggleSelect("src/index.ts", false, tree));
      const paths = getPaths(result);
      expect(paths.has("src")).toBe(true);
      expect(paths.has("!src/index.ts")).toBe(true);
    });

    it("removes exclusion when excluded path is toggled (no parent selected)", () => {
      const { result } = renderSelection([], ["src/index.ts"]);
      act(() => result.current.toggleSelect("src/index.ts", false, null));
      const paths = getPaths(result);
      expect(paths.has("!src/index.ts")).toBe(false);
    });

    it("re-adds exclusion when toggling excluded child of selected parent", () => {
      const { result } = renderSelection(["src"], ["src/index.ts"]);
      act(() => result.current.toggleSelect("src/index.ts", false, null));
      expect(getPaths(result).has("!src/index.ts")).toBe(true);
    });

    it("deselecting a dir removes it and clears child exclusions", () => {
      const { result } = renderSelection(["src"], ["src/index.ts"]);
      act(() => result.current.toggleSelect("src", true, tree));
      const paths = getPaths(result);
      expect(paths.has("src")).toBe(false);
      expect(paths.has("!src/index.ts")).toBe(false);
    });
  });

  describe("isPathExcluded", () => {
    it("returns true when path has exclusion prefix", () => {
      const { result } = renderSelection(["src"], ["src/index.ts"]);
      expect(result.current.isPathExcluded("src/index.ts")).toBe(true);
    });

    it("returns false when path has no exclusion", () => {
      const { result } = renderSelection(["src"]);
      expect(result.current.isPathExcluded("src/index.ts")).toBe(false);
    });
  });

  describe("includedPaths / excludedPaths", () => {
    it("separates included and excluded paths", () => {
      const { result } = renderSelection(["src"], ["src/index.ts"]);
      expect(result.current.includedPaths).toEqual(["src"]);
      expect(result.current.excludedPaths).toEqual(["src/index.ts"]);
    });

    it("returns empty arrays when nothing selected", () => {
      const { result } = renderSelection();
      expect(result.current.includedPaths).toEqual([]);
      expect(result.current.excludedPaths).toEqual([]);
    });
  });
});
