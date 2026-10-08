import { describe, it, expect, vi, afterEach } from "vitest";
import { notifications } from "../notifications.ts";

const created: { title: string; options?: NotificationOptions; instance: FakeNotification }[] = [];

class FakeNotification {
  static permission: NotificationPermission = "granted";
  static requestPermission = vi.fn(() => Promise.resolve("granted" as NotificationPermission));
  onclick: (() => void) | null = null;
  constructor(title: string, options?: NotificationOptions) {
    this.title = title;
    this.options = options;
    created.push({ title, options, instance: this });
  }
  title: string;
  options?: NotificationOptions;
}

function stubNotification(permission: NotificationPermission) {
  FakeNotification.permission = permission;
  vi.stubGlobal("Notification", FakeNotification);
}

function stubVisibility(state: DocumentVisibilityState) {
  Object.defineProperty(document, "visibilityState", {
    value: state,
    configurable: true,
  });
}

describe("notifications", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    stubVisibility("visible");
    created.length = 0;
    FakeNotification.requestPermission.mockClear();
  });

  it("shows a notification when hidden and permission is granted", () => {
    stubNotification("granted");
    stubVisibility("hidden");
    const focus = vi.fn();
    vi.stubGlobal("focus", focus);

    notifications.notifyWhenHidden("chat-a", "the answer");

    expect(created).toHaveLength(1);
    expect(created[0].title).toBe("chat-a");
    expect(created[0].options?.body).toBe("the answer");
    created[0].instance.onclick!();
    expect(focus).toHaveBeenCalled();
  });

  it("truncates long bodies to a single-line snippet", () => {
    stubNotification("granted");
    stubVisibility("hidden");

    notifications.notifyWhenHidden("chat-a", `line one\n${"x".repeat(200)}`);

    const body = created[0].options?.body ?? "";
    expect(body.length).toBe(120);
    expect(body.startsWith("line one x")).toBe(true);
    expect(body.endsWith("…")).toBe(true);
  });

  it("does nothing when the tab is visible", () => {
    stubNotification("granted");
    stubVisibility("visible");

    notifications.notifyWhenHidden("chat-a", "the answer");

    expect(created).toHaveLength(0);
  });

  it("does nothing when permission is not granted", () => {
    stubNotification("default");
    stubVisibility("hidden");

    notifications.notifyWhenHidden("chat-a", "the answer");

    expect(created).toHaveLength(0);
  });

  it("requests permission only when it is undecided", () => {
    stubNotification("denied");
    notifications.requestPermission();
    expect(FakeNotification.requestPermission).not.toHaveBeenCalled();

    stubNotification("default");
    notifications.requestPermission();
    expect(FakeNotification.requestPermission).toHaveBeenCalled();
  });
});
