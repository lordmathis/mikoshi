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

const KANBAN_ENTRIES: FrontmatterEntry[] = [
  { path: "tasks/a.md", frontmatter: { status: "doing" } },
  { path: "tasks/b.md", frontmatter: { status: "todo" } },
  { path: "tasks/c.md", frontmatter: { status: "doing" } },
  { path: "tasks/d.md", frontmatter: {} },
];

async function renderKanban(query: string, entries: FrontmatterEntry[]) {
  const utils = renderView(query, entries);
  await waitFor(() => {
    expect(utils.container.querySelector("[data-lane]")).not.toBeNull();
  });
  return utils;
}

function laneLabels(container: HTMLElement): (string | null)[] {
  return Array.from(container.querySelectorAll("[data-lane]")).map((el) =>
    el.getAttribute("data-lane")
  );
}

function laneCardTitles(container: HTMLElement, lane: string): (string | null)[] {
  const el = container.querySelector(`[data-lane="${lane}"]`);
  return el
    ? Array.from(el.querySelectorAll("a")).map((a) => a.getAttribute("title"))
    : [];
}

describe("ViewBlock", () => {
  it("renders a row per entry with linked file names and passes the glob", async () => {
    const { container, spy } = renderView("glob: specs/**/*.md", ENTRIES);

    await waitFor(() => {
      expect(container.querySelector("table")).not.toBeNull();
    });

    expect(spy).toHaveBeenCalledWith("ws-1", "specs/**/*.md");

    const links = Array.from(container.querySelectorAll("tbody a"));
    expect(links.map((l) => l.textContent)).toEqual(["specs/alpha.md", "specs/beta.md"]);
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
    expect(firstRowCells[0].textContent).toBe("specs/alpha.md");
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

  it("groups cards into lanes by group_by in first-appearance order", async () => {
    const { container } = await renderKanban("display: kanban\ngroup_by: status", KANBAN_ENTRIES);

    expect(laneLabels(container)).toEqual(["doing", "todo", "No status"]);
    expect(laneCardTitles(container, "doing")).toEqual(["tasks/a.md", "tasks/c.md"]);
    expect(laneCardTitles(container, "todo")).toEqual(["tasks/b.md"]);
    expect(laneCardTitles(container, "No status")).toEqual(["tasks/d.md"]);
  });

  it("honors explicit lane order, renders empty lanes, and overflows to Other and No-key lanes", async () => {
    const entries: FrontmatterEntry[] = [
      { path: "t/a.md", frontmatter: { status: "doing" } },
      { path: "t/b.md", frontmatter: { status: "todo" } },
      { path: "t/c.md", frontmatter: { status: "wip" } },
      { path: "t/d.md", frontmatter: {} },
    ];
    const { container } = await renderKanban(
      "display: kanban\ngroup_by: status\nlanes: [todo, done, doing]",
      entries
    );

    expect(laneLabels(container)).toEqual(["todo", "done", "doing", "Other", "No status"]);
    expect(laneCardTitles(container, "done")).toEqual([]);
    expect(laneCardTitles(container, "Other")).toEqual(["t/c.md"]);
  });

  it("sorts cards within lanes by the sort key", async () => {
    const entries: FrontmatterEntry[] = [
      { path: "t/a.md", frontmatter: { status: "doing", priority: 1 } },
      { path: "t/b.md", frontmatter: { status: "doing", priority: 3 } },
      { path: "t/c.md", frontmatter: { status: "doing", priority: 2 } },
    ];
    const { container } = await renderKanban(
      "display: kanban\ngroup_by: status\nsort: -priority",
      entries
    );

    expect(laneCardTitles(container, "doing")).toEqual(["t/b.md", "t/c.md", "t/a.md"]);
  });

  it("calls onFileClick with the full path when a kanban card is clicked", async () => {
    const { container, onFileClick } = await renderKanban(
      "display: kanban\ngroup_by: status",
      KANBAN_ENTRIES
    );

    const link = container.querySelector<HTMLAnchorElement>('[data-lane="doing"] a');
    expect(link).not.toBeNull();
    if (link) fireEvent.click(link);
    expect(onFileClick).toHaveBeenCalledWith("tasks/a.md");
  });

  it("errors when display kanban has no group_by", () => {
    const { container } = renderView("display: kanban", KANBAN_ENTRIES);

    expect(container.querySelector("[data-lane]")).toBeNull();
    expect(container.querySelector("table")).toBeNull();
    expect(container.textContent).toContain("group_by");
  });
});
