import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ChatView } from "../chat-view.tsx";
import { api, type Chat, type ChatWithMessages, type Workspace } from "../../lib/api.ts";

const now = new Date().toISOString();

function node(id: string, name: string): Workspace {
  return { id, name, repo_url: null, connector: null, created_at: now, updated_at: now };
}

const NODE_A = node("ws-a", "Alpha");
const NODE_B = node("ws-b", "Beta");

function listChat(workspaceId: string | null): Chat {
  return { id: "chat-s", title: "Session One", created_at: now, updated_at: now, workspace_id: workspaceId };
}

function fullChat(workspaceId: string | null): ChatWithMessages {
  return { id: "chat-s", title: "Session One", created_at: now, updated_at: now, workspace_id: workspaceId, messages: [] };
}

const desktopMatchMedia = () =>
  vi.fn().mockReturnValue({
    matches: true,
    media: "",
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  });

async function openSessionOnNodeA() {
  render(<ChatView />);
  fireEvent.click(await screen.findByText("Session One"));
  await waitFor(() => expect(window.location.pathname).toBe("/chat/chat-s"));
  // Selecting the session syncs its node into the active workspace (banner).
  await waitFor(() => expect(screen.getByText("Bound to: Alpha")).toBeTruthy());
}

describe("ChatView session/node selection", () => {
  beforeEach(() => {
    localStorage.clear();
    window.history.replaceState({}, "", "/");
    (window as unknown as { matchMedia: ReturnType<typeof desktopMatchMedia> }).matchMedia =
      desktopMatchMedia();
    vi.spyOn(api, "listWorkspaces").mockResolvedValue({
      workspaces: [NODE_A, NODE_B],
    });
    vi.spyOn(api, "listChats").mockImplementation(
      (_limit?: number, _offset?: number, workspaceId?: string | null) =>
        Promise.resolve({ chats: workspaceId === NODE_B.id ? [] : [listChat(NODE_A.id)] })
    );
    vi.spyOn(api, "getChat").mockResolvedValue(fullChat(NODE_A.id));
    vi.spyOn(api, "getDefaultChatConfig").mockResolvedValue({ model: "test-model", tool_servers: [] });
    vi.spyOn(api, "getStreamStatus").mockResolvedValue({ active: false });
    vi.spyOn(api, "listApprovals").mockResolvedValue({ approvals: [] });
    vi.spyOn(api, "listSkills").mockResolvedValue({ skills: [] });
    vi.spyOn(api, "getWorkspaceFileList").mockResolvedValue([]);
    vi.spyOn(api, "getWorkspaceTree").mockResolvedValue({
      path: "/",
      name: "/",
      type: "dir",
      children: [],
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("deselects the session when selecting a node it does not belong to", async () => {
    await openSessionOnNodeA();

    fireEvent.click(screen.getByText("Nodes"));
    fireEvent.click(screen.getByText("Beta"));

    await waitFor(() => expect(window.location.pathname).toBe("/"));
    expect(api.listChats).toHaveBeenCalledWith(20, 0, NODE_B.id);

    // The foreign session must not reappear in the node-filtered list.
    fireEvent.click(screen.getByText("Sessions"));
    await waitFor(() => expect(screen.queryByText("Session One")).toBeNull());
  });

  it("deselects the session when the node filter is unbound", async () => {
    await openSessionOnNodeA();

    const banner = screen.getByText("Bound to: Alpha").closest("div")!;
    fireEvent.click(banner.querySelector("button")!);

    await waitFor(() => expect(window.location.pathname).toBe("/"));
    await waitFor(() => expect(screen.queryByText("Bound to: Alpha")).toBeNull());
    expect(api.listChats).toHaveBeenCalledWith(20, 0, null);
    expect(document.title).toBe("Mikoshi Chat");
  });
});
