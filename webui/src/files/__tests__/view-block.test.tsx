import { describe, it, expect, vi, afterEach } from "vitest";
import { render, waitFor, fireEvent } from "@testing-library/react";
import { ViewBlock, ViewBlockContext } from "../view-block.tsx";
import { api, type FrontmatterEntry } from "../../lib/api.ts";

function renderView(query: string, entries: FrontmatterEntry[] = []) {
  const onFileClick = vi.fn();
  const spy = vi.spyOn(api, "getWorkspaceFrontmatter").mockResolvedValue(entries);
  const utils = render(
    <ViewBlockContext.Provider value={{ workspaceId: "ws-1", onFileClick }}>
      <ViewBlock query={query} />
    </ViewBlockContext.Provider>
  );
  return { ...utils, onFileClick, spy };
}

afterEach(() => {
  vi.restoreAllMocks();
});

const ENTRIES: FrontmatterEntry[] = [
  { path: "specs/beta.md", frontmatter: { status: "done", priority: 1 } },
  { path: "specs/alpha.md", frontmatter: { status: "draft", priority: 2 } },
];

describe("ViewBlock", () => {
  it("renders a row per entry with linked file names and passes the glob", async () => {
    const { container, spy } = renderView("glob: specs/**/*.md", ENTRIES);

    await waitFor(() => {
      expect(container.querySelector("table")).not.toBeNull();
    });

    expect(spy).toHaveBeenCalledWith("ws-1", "specs/**/*.md");

    const links = Array.from(container.querySelectorAll("tbody a"));
    expect(links.map((l) => l.textContent)).toEqual(["alpha.md", "beta.md"]);
  });

  it("defaults columns to the union of frontmatter keys", async () => {
    const { container } = renderView("", ENTRIES);

    await waitFor(() => {
      expect(container.querySelector("table")).not.toBeNull();
    });

    const headers = Array.from(container.querySelectorAll("th")).map(
      (th) => th.textContent
    );
    expect(headers).toEqual(["File", "status", "priority"]);
  });

  it("shows only the requested columns and sorts descending with '-' prefix", async () => {
    const { container } = renderView("columns: [status]\nsort: -priority", ENTRIES);

    await waitFor(() => {
      expect(container.querySelector("table")).not.toBeNull();
    });

    const headers = Array.from(container.querySelectorAll("th")).map(
      (th) => th.textContent
    );
    expect(headers).toEqual(["File", "status"]);

    const firstRowCells = container.querySelectorAll("tbody tr")[0].querySelectorAll("td");
    expect(firstRowCells[0].textContent).toBe("alpha.md");
    expect(firstRowCells[1].textContent).toBe("draft");
  });

  it("renders missing values as a dash", async () => {
    const entries = [{ path: "a.md", frontmatter: { status: "draft" } }];
    const { container } = renderView("columns: [status, missing]", entries);

    await waitFor(() => {
      expect(container.querySelector("table")).not.toBeNull();
    });

    const cells = container.querySelectorAll("tbody tr")[0].querySelectorAll("td");
    expect(cells[2].textContent).toContain("—");
  });

  it("calls onFileClick with the full path when a file link is clicked", async () => {
    const { container, onFileClick } = renderView("", ENTRIES);

    await waitFor(() => {
      expect(container.querySelector("table")).not.toBeNull();
    });

    fireEvent.click(container.querySelectorAll("tbody a")[0]);
    expect(onFileClick).toHaveBeenCalledWith("specs/alpha.md");
  });

  it("accepts a leading-* glob without yaml alias errors", async () => {
    const { container, spy } = renderView("glob: **/*.md", ENTRIES);

    await waitFor(() => {
      expect(container.querySelector("table")).not.toBeNull();
    });

    expect(spy).toHaveBeenCalledWith("ws-1", "**/*.md");
  });

  it("renders an error box for invalid query yaml", () => {
    const { container } = renderView("glob: [unclosed");

    expect(container.querySelector("table")).toBeNull();
    expect(container.textContent).toBeTruthy();
  });

  it("degrades to a code block outside preview context without fetching", () => {
    const spy = vi.spyOn(api, "getWorkspaceFrontmatter").mockResolvedValue([]);
    const { container } = render(<ViewBlock query="glob: specs/**/*.md" />);

    expect(container.querySelector("table")).toBeNull();
    expect(spy).not.toHaveBeenCalled();
  });
});
