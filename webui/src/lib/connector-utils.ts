import { api } from "./api";

export async function fetchAllFilePaths(
  connector: string,
  resource: string,
  path: string = ""
): Promise<string[]> {
  const paths: string[] = [];
  try {
    const node = await api.browseConnectorTree(connector, resource, path);
    if (node.type === "file") {
      paths.push(node.path);
    } else if (node.children) {
      for (const child of node.children) {
        if (child.type === "file") {
          paths.push(child.path);
        } else if (child.type === "dir") {
          paths.push(...(await fetchAllFilePaths(connector, resource, child.path)));
        }
      }
    }
  } catch {
    // skip subtrees that fail
  }
  return paths;
}

export function matchesPatterns(filePath: string, patterns: string): boolean {
  const fileName = filePath.split("/").pop() ?? filePath;
  return patterns
    .split(",")
    .map((p) => p.trim())
    .filter(Boolean)
    .some((pattern) => {
      const regex = new RegExp(
        "^" + pattern.split("*").map((s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("[^/]*") + "$"
      );
      return regex.test(fileName) || regex.test(filePath);
    });
}