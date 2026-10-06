import { describe, it, expect } from "vitest";
import { formatValue, parseFrontmatter } from "../frontmatter.ts";

describe("parseFrontmatter", () => {
  it("parses scalars, lists, and nested maps", () => {
    const result = parseFrontmatter(
      "---\nstatus: draft\npriority: 2\ndone: false\ntags:\n  - a\n  - b\nmeta:\n  owner: me\n---\nbody"
    );

    expect(result).not.toBeNull();
    expect(result!.metadata).toEqual({
      status: "draft",
      priority: 2,
      done: false,
      tags: ["a", "b"],
      meta: { owner: "me" },
    });
    expect(result!.content).toBe("body");
  });

  it("returns null when no frontmatter", () => {
    expect(parseFrontmatter("just some markdown")).toBeNull();
    expect(parseFrontmatter("")).toBeNull();
  });

  it("returns null on invalid yaml", () => {
    expect(parseFrontmatter("---\nstatus: [unclosed\n---\nbody")).toBeNull();
  });

  it("returns null on non-dict frontmatter", () => {
    expect(parseFrontmatter("---\n- a\n- b\n---\nbody")).toBeNull();
  });

  it("returns null on empty frontmatter", () => {
    expect(parseFrontmatter("---\n---\nbody")).toBeNull();
  });
});

describe("formatValue", () => {
  it("formats primitives", () => {
    expect(formatValue(null)).toBe("null");
    expect(formatValue(undefined)).toBe("null");
    expect(formatValue(true)).toBe("true");
    expect(formatValue(3)).toBe("3");
    expect(formatValue("x")).toBe("x");
  });

  it("formats lists and objects", () => {
    expect(formatValue(["a", "b"])).toBe("a, b");
    expect(formatValue({ a: 1 })).toBe('{"a":1}');
  });
});
