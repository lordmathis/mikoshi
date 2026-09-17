import { describe, it, expect } from "vitest";
import { mergeChildren } from "../workspace-tree.tsx";
import type { FileNode } from "../../lib/api.ts";

const node = (path: string, children?: FileNode[]): FileNode => ({
  path,
  name: path.split("/").pop() || "",
  type: "dir",
  ...(children ? { children } : {}),
});

describe("mergeChildren", () => {
  it("attaches children to the exact target node", () => {
    const tree = node("", [node("foo"), node("bar")]);
    const kids = [node("foo/qux")];

    const merged = mergeChildren(tree, "foo", kids);

    expect(merged.children!.find((c) => c.path === "foo")!.children).toEqual(kids);
  });

  it("does not recurse into a sibling that only shares a path prefix", () => {
    const fooBar = node("foo/bar");
    const tree = node("", [node("foo", [fooBar]), node("foo/bar-baz")]);

    const merged = mergeChildren(tree, "foo/bar-baz/sub", [node("foo/bar-baz/sub/x")]);

    const fooBarAfter = merged.children!.find((c) => c.path === "foo")!.children!.find((c) => c.path === "foo/bar");
    expect(fooBarAfter).toBe(fooBar);
    expect(merged.children!.find((c) => c.path === "foo/bar-baz")!.children).toBeUndefined();
  });

  it("returns the tree unchanged when the target path is absent", () => {
    const tree = node("", [node("foo")]);
    const merged = mergeChildren(tree, "baz/sub", [node("baz/sub/x")]);
    expect(merged).toEqual(tree);
  });
});
