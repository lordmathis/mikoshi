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

export function remarkWikiLinks() {
  return (tree: Root) => {
    visit(tree, "text", (node, index, parent) => {
      if (!parent || index === null || index === undefined) return;

      const value = node.value;
      if (!value.includes("[[")) return;

      const segments: MdastNode[] = [];
      let lastIndex = 0;
      let match: RegExpExecArray | null;

      const combinedRe = /!\[\[([^\]]+)\]\]|\[\[([^\]]+?)\]\]/g;

      while ((match = combinedRe.exec(value)) !== null) {
        if (match.index > lastIndex) {
          segments.push(textNode(value.slice(lastIndex, match.index)));
        }

        const imageTarget = match[1];
        const linkTarget = match[2];

        if (imageTarget) {
          segments.push(wikiImageNode(imageTarget));
        } else if (linkTarget) {
          const withoutDisplay = linkTarget.split("|")[0];
          const target = withoutDisplay.split("#")[0];
          const displayOverride = linkTarget.split("|")[1];
          const label = displayOverride || withoutDisplay.split("/").pop()!;
          segments.push(wikiLinkNode(target, label));
        }

        lastIndex = combinedRe.lastIndex;
      }

      if (lastIndex < value.length) {
        segments.push(textNode(value.slice(lastIndex)));
      }

      if (segments.length > 0) {
        parent.children.splice(index, 1, ...segments);
        return index + segments.length;
      }
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
