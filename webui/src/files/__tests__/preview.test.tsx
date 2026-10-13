import { describe, it, expect, vi } from "vitest";
import { render, fireEvent } from "@testing-library/react";
import { FrontmatterPanel } from "../preview.tsx";

function renderPanel(
  metadata: Record<string, unknown>,
  fileIndex: Map<string, string> = new Map()
) {
  const onFileClick = vi.fn();
  const utils = render(
    <FrontmatterPanel
      metadata={metadata}
      workspaceId="ws-1"
      fileIndex={fileIndex}
      onFileClick={onFileClick}
    />
  );
  return { ...utils, onFileClick };
}

describe("FrontmatterPanel", () => {
  it("renders plain values as text without links", () => {
    const { container } = renderPanel({ status: "draft", priority: 2 });

    expect(container.textContent).toContain("status");
    expect(container.textContent).toContain("draft");
    expect(container.querySelectorAll("a")).toHaveLength(0);
  });

  it("renders a resolved wiki link as a link to the target file", () => {
    const { container, onFileClick } = renderPanel(
      { related: "[[note]]" },
      new Map([["note.md", "notes/note.md"]])
    );

    const link = container.querySelector("a");
    expect(link?.textContent).toBe("note");
    fireEvent.click(link!);
    expect(onFileClick).toHaveBeenCalledWith("notes/note.md");
  });

  it("renders an unresolved wiki link as raw chip text", () => {
    const { container } = renderPanel({ related: "[[missing]]" });

    expect(container.textContent).toContain("[[missing]]");
    expect(container.querySelectorAll("a")).toHaveLength(0);
  });

  it("renders each wiki link in an array value", () => {
    const { container } = renderPanel(
      { related: ["[[a]]", "[[b]]"] },
      new Map([
        ["a.md", "a.md"],
        ["b.md", "b.md"],
      ])
    );

    const links = container.querySelectorAll("a");
    expect(Array.from(links).map((l) => l.textContent)).toEqual(["a", "b"]);
  });
});
