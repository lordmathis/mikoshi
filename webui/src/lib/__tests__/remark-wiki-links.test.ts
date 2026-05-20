import { describe, it, expect } from "vitest";
import { remarkWikiLinks, resolveTarget } from "../remark-wiki-links";
import type { Root } from "mdast";

function makeTree(text: string): Root {
  return {
    type: "root",
    children: [
      {
        type: "paragraph",
        children: [{ type: "text", value: text }],
      },
    ],
  };
}

function applyPlugin(tree: Root): Root {
  const plugin = remarkWikiLinks();
  plugin(tree);
  return tree;
}

function collectLinks(tree: Root) {
  const links: Array<{ url: string; text: string }> = [];
  function walk(node: any) {
    if (node.type === "link") {
      const text = node.children
        ?.filter((c: any) => c.type === "text")
        .map((c: any) => c.value)
        .join("");
      links.push({ url: node.url, text: text ?? "" });
    }
    if (node.children) node.children.forEach(walk);
  }
  walk(tree);
  return links;
}

function collectTexts(tree: Root) {
  const texts: string[] = [];
  function walk(node: any) {
    if (node.type === "text") texts.push(node.value);
    if (node.children) node.children.forEach(walk);
  }
  walk(tree);
  return texts;
}

describe("remarkWikiLinks", () => {
  it("parses [[Page Name]] into link node", () => {
    const tree = applyPlugin(makeTree("[[Page Name]]"));
    const links = collectLinks(tree);
    expect(links).toHaveLength(1);
    expect(links[0].url).toBe("wiki://Page Name");
    expect(links[0].text).toBe("Page Name");
  });

  it("handles display override with pipe [[page|display]]", () => {
    const tree = applyPlugin(makeTree("[[page|display]]"));
    const links = collectLinks(tree);
    expect(links).toHaveLength(1);
    expect(links[0].url).toBe("wiki://page");
    expect(links[0].text).toBe("display");
  });

  it("strips heading fragment from target [[page#heading]]", () => {
    const tree = applyPlugin(makeTree("[[page#heading]]"));
    const links = collectLinks(tree);
    expect(links[0].url).toBe("wiki://page");
  });

  it("parses image embed ![[image.png]]", () => {
    const tree = applyPlugin(makeTree("![[image.png]]"));
    const links = collectLinks(tree);
    expect(links).toHaveLength(1);
    expect(links[0].url).toBe("wiki-image://image.png");
  });

  it("splits text around link: 'before [[link]] after'", () => {
    const tree = applyPlugin(makeTree("Text before [[link]] text after"));
    const texts = collectTexts(tree);
    expect(texts).toContain("Text before ");
    expect(texts).toContain(" text after");
  });

  it("handles two links in sequence", () => {
    const tree = applyPlugin(makeTree("[[link]] and [[another]]"));
    const links = collectLinks(tree);
    expect(links).toHaveLength(2);
  });

  it("leaves text without links unchanged", () => {
    const tree = applyPlugin(makeTree("No links here"));
    const links = collectLinks(tree);
    expect(links).toHaveLength(0);
    expect(collectTexts(tree)).toContain("No links here");
  });

  it("leaves malformed [[link unchanged (no closing brackets)", () => {
    const tree = applyPlugin(makeTree("Malformed [[link"));
    const links = collectLinks(tree);
    expect(links).toHaveLength(0);
    expect(collectTexts(tree)).toContain("Malformed [[link");
  });
});

describe("resolveTarget", () => {
  it("returns target as-is when it contains /", () => {
    expect(resolveTarget("path/to/file.md", new Map())).toBe("path/to/file.md");
  });

  it("returns indexed path for exact match", () => {
    const index = new Map([["readme.md", "vault/readme.md"]]);
    expect(resolveTarget("readme.md", index)).toBe("vault/readme.md");
  });

  it("appends .md and resolves from index when target has no extension", () => {
    const index = new Map([["readme.md", "vault/readme.md"]]);
    expect(resolveTarget("readme", index)).toBe("vault/readme.md");
  });

  it("does not append .md for image targets", () => {
    const index = new Map([["photo.png", "assets/photo.png"]]);
    expect(resolveTarget("photo.png", index)).toBe("assets/photo.png");
  });

  it("returns null when target is not found", () => {
    expect(resolveTarget("missing", new Map())).toBeNull();
  });

  it("resolves case-insensitively", () => {
    const index = new Map([["readme.md", "vault/readme.md"]]);
    expect(resolveTarget("README", index)).toBe("vault/readme.md");
  });
});
