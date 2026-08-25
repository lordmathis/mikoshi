import { describe, it, expect } from "vitest";
import { encodeFilePath } from "../api";

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
