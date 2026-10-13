import { visit } from "unist-util-visit";
import type { Root, Text, Link } from "mdast";

const IMAGE_EXTENSIONS = new Set([
  ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp", ".ico",
  ".tiff", ".tif", ".avif",
]);

function textNode(value: string): Text {
  return { type: "text", value };
}

function wikiImageNode(target: string): Link {
  return {
    type: "link",
    url: `wiki-image://${target}`,
    title: null,
    children: [{ type: "text", value: `![[${target}]]` }],
  };
}

function wikiLinkNode(href: string, label: string): Link {
  return {
    type: "link",
    url: `wiki://${href}`,
    title: null,
    children: [{ type: "text", value: label }],
  };
}

function isImageFilename(name: string): boolean {
  const dotIndex = name.lastIndexOf(".");
  if (dotIndex === -1) return false;
  const ext = name.slice(dotIndex).toLowerCase();
  return IMAGE_EXTENSIONS.has(ext);
}

function addMarkdownExtension(name: string): string {
  if (name.includes(".")) return name;
  return name + ".md";
}

type MdastNode = Text | Link;

export type WikiSegment =
  | { kind: "text"; value: string }
  | { kind: "link"; target: string; label: string; raw: string }
  | { kind: "image"; target: string; raw: string };

function parseLinkTarget(linkTarget: string, raw: string): WikiSegment {
  const withoutDisplay = linkTarget.split("|")[0];
  const target = withoutDisplay.split("#")[0];
  const displayOverride = linkTarget.split("|")[1];
  const label = displayOverride || withoutDisplay.split("/").pop()!;
  return { kind: "link", target, label, raw };
}

export function parseWikiLinks(text: string): WikiSegment[] {
  if (!text.includes("[[")) return [{ kind: "text", value: text }];

  const segments: WikiSegment[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  const combinedRe = /!\[\[([^\]]+)\]\]|\[\[([^\]]+?)\]\]/g;

  while ((match = combinedRe.exec(text)) !== null) {
    if (match.index > lastIndex) {
      segments.push({ kind: "text", value: text.slice(lastIndex, match.index) });
    }

    if (match[1] !== undefined) {
      segments.push({ kind: "image", target: match[1], raw: match[0] });
    } else {
      segments.push(parseLinkTarget(match[2], match[0]));
    }

    lastIndex = combinedRe.lastIndex;
  }

  if (lastIndex < text.length) {
    segments.push({ kind: "text", value: text.slice(lastIndex) });
  }

  return segments.length > 0 ? segments : [{ kind: "text", value: text }];
}

function segmentToMdast(segment: WikiSegment): MdastNode {
  if (segment.kind === "text") return textNode(segment.value);
  if (segment.kind === "image") return wikiImageNode(segment.target);
  return wikiLinkNode(segment.target, segment.label);
}

export function remarkWikiLinks() {
  return (tree: Root) => {
    visit(tree, "text", (node, index, parent) => {
      if (!parent || index === null || index === undefined) return;

      const segments = parseWikiLinks(node.value);
      const isPlain = segments.length === 1 && segments[0].kind === "text";
      if (isPlain) return;

      const nodes = segments.map(segmentToMdast);
      parent.children.splice(index, 1, ...nodes);
      return index + nodes.length;
    });
  };
}

export function resolveTarget(
  target: string,
  fileIndex: Map<string, string>
): string | null {
  if (target.includes("/")) return target;

  let resolved = fileIndex.get(target.toLowerCase());
  if (resolved) return resolved;

  if (!isImageFilename(target)) {
    const withExt = addMarkdownExtension(target);
    resolved = fileIndex.get(withExt.toLowerCase());
    if (resolved) return resolved;
  }

  return null;
}
