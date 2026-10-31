import { isValidElement, type ComponentProps, type ReactNode } from "react";
import type { Components, ExtraProps } from "react-markdown";
import type { PluggableList } from "unified";
import remarkGfm from "remark-gfm";
import remarkBreaks from "remark-breaks";
import remarkEmoji from "remark-emoji";
import remarkGithubAlerts from "remark-github-alerts";
import { Mermaid } from "./mermaid.tsx";
import { CodeBlock } from "./code-block.tsx";
import { ViewBlock } from "../files/view-block.tsx";

export const REMARK_PLUGINS: PluggableList = [
  remarkGfm,
  remarkBreaks,
  [remarkEmoji, { emoticon: true }],
  remarkGithubAlerts,
];

const isMermaid = (className: string | undefined) =>
  /language-mermaid/.test(className || "");

const isView = (className: string | undefined) =>
  /language-view\b/.test(className || "");

const baseTableComponents = (rgbVar: string): Components => ({
  table: ({ children, node: _node, ...props }: ComponentProps<'table'> & ExtraProps) => (
    <div className="overflow-x-auto mb-4">
      <table className="w-full border-collapse border" style={{ borderColor: `rgb(var(${rgbVar}) / 0.2)` }} {...props}>{children}</table>
    </div>
  ),
  thead: ({ children, node: _node, ...props }: ComponentProps<'thead'> & ExtraProps) => (
    <thead style={{ backgroundColor: `rgb(var(${rgbVar}) / 0.06)` }} {...props}>{children}</thead>
  ),
  th: ({ children, node: _node, ...props }: ComponentProps<'th'> & ExtraProps) => (
    <th className="px-3 py-2 text-left text-sm font-bold text-foreground" style={{ borderWidth: '1px', borderStyle: 'solid', borderColor: `rgb(var(${rgbVar}) / 0.2)` }} {...props}>{children}</th>
  ),
  td: ({ children, node: _node, ...props }: ComponentProps<'td'> & ExtraProps) => (
    <td className="px-3 py-2 text-sm text-foreground/80" style={{ borderWidth: '1px', borderStyle: 'solid', borderColor: `rgb(var(${rgbVar}) / 0.15)` }} {...props}>{children}</td>
  ),
  tr: ({ children, node: _node, ...props }: ComponentProps<'tr'> & ExtraProps) => (
    <tr className="even:bg-primary/3" {...props}>{children}</tr>
  ),
});

type CodeElementProps = { className?: string; children?: ReactNode };

function nodeToText(node: ReactNode): string {
  if (node === null || node === undefined || typeof node === "boolean") return "";
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(nodeToText).join("");
  if (isValidElement<CodeElementProps>(node)) return nodeToText(node.props.children);
  return "";
}

function codeChildProps(children: ReactNode | undefined): CodeElementProps | undefined {
  const child: unknown = Array.isArray(children) ? children[0] : children;
  return isValidElement<CodeElementProps>(child) ? child.props : undefined;
}

const baseCodeComponents = (rgbVar: string): Components => ({
  code: ({ className, children, node: _node, ...props }: ComponentProps<'code'> & ExtraProps) => {
    if (isMermaid(className)) {
      return <Mermaid chart={nodeToText(children).replace(/\n$/, "")} />;
    }
    return (
      <code
        className="px-1.5 py-0.5 text-xs break-words"
        style={{ backgroundColor: `rgb(var(${rgbVar}) / 0.08)`, color: `rgb(var(${rgbVar}) / 0.9)` }}
        {...props}
      >
        {children}
      </code>
    );
  },
  pre: ({ children, node: _node, ...props }: ComponentProps<'pre'> & ExtraProps) => {
    const childProps = codeChildProps(children);
    if (childProps && isMermaid(childProps.className)) {
      return <>{children}</>;
    }
    if (childProps && isView(childProps.className)) {
      return <ViewBlock query={nodeToText(childProps.children).replace(/\n$/, "")} />;
    }
    if (childProps) {
      const match = /language-(\S+)/.exec(childProps.className || "");
      const lang = match ? match[1].toLowerCase() : "text";
      const code = nodeToText(childProps.children).replace(/\n$/, "");
      return <CodeBlock code={code} lang={lang} />;
    }
    return <pre className="overflow-x-auto mb-4 text-sm" {...props}>{children}</pre>;
  },
});

export const markdownComponents: Components = {
  h1: ({ children, node: _node, ...props }: ComponentProps<'h1'> & ExtraProps) => (
    <h1 className="text-2xl font-bold mt-6 mb-4 first:mt-0 text-foreground" {...props}>{children}</h1>
  ),
  h2: ({ children, node: _node, ...props }: ComponentProps<'h2'> & ExtraProps) => (
    <h2 className="text-xl font-bold mt-5 mb-3 first:mt-0 text-foreground" {...props}>{children}</h2>
  ),
  h3: ({ children, node: _node, ...props }: ComponentProps<'h3'> & ExtraProps) => (
    <h3 className="text-lg font-bold mt-4 mb-2 first:mt-0 text-foreground" {...props}>{children}</h3>
  ),
  h4: ({ children, node: _node, ...props }: ComponentProps<'h4'> & ExtraProps) => (
    <h4 className="text-base font-bold mt-3 mb-2 first:mt-0 text-foreground" {...props}>{children}</h4>
  ),
  p: ({ children, node: _node, ...props }: ComponentProps<'p'> & ExtraProps) => (
    <p className="mb-4 last:mb-0 text-foreground/90" {...props}>{children}</p>
  ),
  ul: ({ children, node: _node, ...props }: ComponentProps<'ul'> & ExtraProps) => (
    <ul className="list-disc pl-6 mb-4 space-y-1" {...props}>{children}</ul>
  ),
  ol: ({ children, node: _node, ...props }: ComponentProps<'ol'> & ExtraProps) => (
    <ol className="list-decimal pl-6 mb-4 space-y-1" {...props}>{children}</ol>
  ),
  li: ({ children, node: _node, ...props }: ComponentProps<'li'> & ExtraProps) => (
    <li {...props}>{children}</li>
  ),
  strong: ({ children, node: _node, ...props }: ComponentProps<'strong'> & ExtraProps) => (
    <strong className="font-bold text-foreground" {...props}>{children}</strong>
  ),
  em: ({ children, node: _node, ...props }: ComponentProps<'em'> & ExtraProps) => (
    <em className="italic" {...props}>{children}</em>
  ),
  blockquote: ({ children, node: _node, ...props }: ComponentProps<'blockquote'> & ExtraProps) => (
    <blockquote className="border-l-2 border-primary/40 pl-4 italic my-4" {...props}>{children}</blockquote>
  ),
  hr: ({ node: _node, ...props }: ComponentProps<'hr'> & ExtraProps) => (
    <hr className="my-6 border-border" {...props} />
  ),
  a: ({ children, href, node: _node, ...props }: ComponentProps<'a'> & ExtraProps) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-[var(--color-cp-cyan)] underline hover:text-[var(--color-cp-cyan)]/80"
      {...props}
    >
      {children}
    </a>
  ),
  ...baseCodeComponents("--cp-rgb-yellow"),
  ...baseTableComponents("--cp-rgb-yellow"),
};

export const cyanMarkdownComponents: Components = {
  ...baseCodeComponents("--cp-rgb-cyan"),
  ...baseTableComponents("--cp-rgb-cyan"),
};
