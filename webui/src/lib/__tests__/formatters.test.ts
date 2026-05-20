import { describe, it, expect, vi, beforeEach } from "vitest";
import { formatTimestamp, getToolLabel, formatModelLabel } from "../formatters";

describe("formatTimestamp", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2025-06-15T12:00:00Z"));
  });

  it("returns 'Just now' for <1 min ago", () => {
    expect(formatTimestamp("2025-06-15T11:59:30Z")).toBe("Just now");
  });

  it("formats minutes with correct pluralization", () => {
    expect(formatTimestamp("2025-06-15T11:59:00Z")).toBe("1 minute ago");
    expect(formatTimestamp("2025-06-15T11:55:00Z")).toBe("5 minutes ago");
  });

  it("formats hours with correct pluralization", () => {
    expect(formatTimestamp("2025-06-15T11:00:00Z")).toBe("1 hour ago");
    expect(formatTimestamp("2025-06-15T07:00:00Z")).toBe("5 hours ago");
  });

  it("returns 'Yesterday' for exactly 1 day ago", () => {
    expect(formatTimestamp("2025-06-14T12:00:00Z")).toBe("Yesterday");
  });

  it("formats days, weeks, months, and years with correct pluralization", () => {
    expect(formatTimestamp("2025-06-13T12:00:00Z")).toBe("2 days ago");
    expect(formatTimestamp("2025-06-08T12:00:00Z")).toBe("1 week ago");
    expect(formatTimestamp("2025-05-16T12:00:00Z")).toBe("1 month ago");
    expect(formatTimestamp("2024-06-15T12:00:00Z")).toBe("1 year ago");
    expect(formatTimestamp("2023-06-15T12:00:00Z")).toBe("2 years ago");
  });
});

describe("getToolLabel", () => {
  it("capitalizes a single word", () => {
    expect(getToolLabel("read")).toBe("Read");
  });

  it("splits underscores into words", () => {
    expect(getToolLabel("my_tool_name")).toBe("My Tool Name");
  });

  it("splits hyphens into words", () => {
    expect(getToolLabel("my-tool-name")).toBe("My Tool Name");
  });

  it("handles mixed delimiters", () => {
    expect(getToolLabel("my_tool-name")).toBe("My Tool Name");
  });
});

describe("formatModelLabel", () => {
  it("strips provider prefix from colon-separated id", () => {
    expect(formatModelLabel("anthropic:claude-3")).toBe("claude-3");
  });

  it("returns id unchanged when no colon present", () => {
    expect(formatModelLabel("gpt-4")).toBe("gpt-4");
  });

  it("only strips first colon segment, preserves rest", () => {
    expect(formatModelLabel("provider:model:extra")).toBe("model:extra");
  });
});
