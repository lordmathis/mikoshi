import { describe, it, expect } from "vitest";
import { render, waitFor } from "@testing-library/react";
import ReactMarkdown from "react-markdown";
import { markdownComponents, REMARK_PLUGINS } from "../markdown-components.tsx";

const renderMarkdown = (source: string) =>
  render(
    <ReactMarkdown remarkPlugins={REMARK_PLUGINS} components={markdownComponents}>
      {source}
    </ReactMarkdown>
  );

describe("markdown pipeline", () => {
  it("renders fenced code blocks through shiki", async () => {
    const { container } = renderMarkdown("```ts\nconst x: number = 1;\n```");

    await waitFor(
      () => {
        const pre = container.querySelector("pre.shiki");
        expect(pre).not.toBeNull();
        expect(pre!.textContent).toContain("const x: number = 1;");
      },
      { timeout: 10000 }
    );
  });

  it("renders unknown languages as plain text without throwing", async () => {
    const { container } = renderMarkdown("```totally-not-a-language\nsome text\n```");

    await waitFor(
      () => {
        expect(container.querySelector("pre.shiki")).not.toBeNull();
      },
      { timeout: 10000 }
    );
  });

  it("converts emoji shortcodes", () => {
    const { container } = renderMarkdown("hello :tada:");

    expect(container.textContent).toContain("hello 🎉");
  });

  it("renders github alerts as styled divs", () => {
    const { container } = renderMarkdown("> [!NOTE]\n> Useful info");

    const alert = container.querySelector(".markdown-alert.markdown-alert-note");
    expect(alert).not.toBeNull();
    expect(container.querySelector(".markdown-alert-title")!.textContent).toContain("Note");
    expect(alert!.textContent).toContain("Useful info");
  });

  it("leaves regular blockquotes untouched", () => {
    const { container } = renderMarkdown("> just a quote");

    expect(container.querySelector("blockquote")).not.toBeNull();
    expect(container.querySelector(".markdown-alert")).toBeNull();
  });
});
