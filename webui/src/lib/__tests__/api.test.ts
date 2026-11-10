import { describe, it, expect, vi, afterEach } from "vitest";
import { ApiError, api, encodeFilePath } from "../api";

const realFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = realFetch;
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

function stubLocation(): ReturnType<typeof vi.fn> {
  const assign = vi.fn();
  Object.defineProperty(window, "location", {
    configurable: true,
    value: { assign },
  });
  return assign;
}

describe("session expiry", () => {
  it("navigates to /login when a failing call probes as an auth redirect", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(1_000_000_000_000);
    const assign = stubLocation();
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockRejectedValueOnce(new TypeError("Failed to fetch"))
        .mockResolvedValueOnce({ status: 0 })
    );

    await expect(api.listChats()).rejects.toMatchObject({
      name: "ApiError",
      status: 401,
    });
    expect(assign).toHaveBeenCalledWith("/login");
  });

  it("rethrows plain network errors when the proxy does not redirect", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(1_000_000_000_000);
    const assign = stubLocation();
    const failure = new TypeError("Failed to fetch");
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockRejectedValueOnce(failure)
        .mockResolvedValueOnce({ status: 200 })
    );

    await expect(api.listChats()).rejects.toBe(failure);
    expect(assign).not.toHaveBeenCalled();
  });

  it("navigates to /login on a direct 401 response", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(1_000_000_010_000);
    const assign = stubLocation();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(null, { status: 401 }))
    );

    await expect(api.listChats()).rejects.toBeInstanceOf(ApiError);
    expect(assign).toHaveBeenCalledWith("/login");
  });

  it("does not probe when a request is aborted", async () => {
    const assign = stubLocation();
    const abort = new DOMException("Aborted", "AbortError");
    const fetchMock = vi.fn().mockRejectedValue(abort);
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.listChats()).rejects.toBe(abort);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(assign).not.toHaveBeenCalled();
  });
});

describe("encodeFilePath", () => {
  it("encodes special characters in each segment but keeps slashes", () => {
    expect(encodeFilePath("docs/my file.md")).toBe("docs/my%20file.md");
    expect(encodeFilePath("a#b/c%d/ünï.txt")).toBe("a%23b/c%25d/%C3%BCn%C3%AF.txt");
  });

  it("leaves plain paths untouched", () => {
    expect(encodeFilePath("src/lib/api.ts")).toBe("src/lib/api.ts");
    expect(encodeFilePath("")).toBe("");
  });
});
