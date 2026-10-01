import remarkGfm from "remark-gfm";
import remarkBreaks from "remark-breaks";
import remarkEmoji from "remark-emoji";
import remarkGithubAlerts from "remark-github-alerts";
import { Mermaid } from "./mermaid.tsx";
import { CodeBlock } from "./code-block.tsx";

export const REMARK_PLUGINS: any[] = [
  remarkGfm,
  remarkBreaks,
  [remarkEmoji, { emoticon: true }],
  remarkGithubAlerts,
];

const isMermaid = (className: string | undefined) =>
  /language-mermaid/.test(className || "");

const baseTableComponents = (rgbVar: string) => ({
  table: ({ children, ...props }: any) => (
    <div className="overflow-x-auto mb-4">
      <table className="w-full border-collapse border" style={{ borderColor: `rgb(var(${rgbVar}) / 0.2)` }} {...props}>{children}</table>
    </div>
  ),
  thead: ({ children, ...props }: any) => (
    <thead style={{ backgroundColor: `rgb(var(${rgbVar}) / 0.06)` }} {...props}>{children}</thead>
  ),
  th: ({ children, ...props }: any) => (
    <th className="px-3 py-2 text-left text-sm font-bold text-foreground" style={{ borderWidth: '1px', borderStyle: 'solid', borderColor: `rgb(var(${rgbVar}) / 0.2)` }} {...props}>{children}</th>
  ),
  td: ({ children, ...props }: any) => (
    <td className="px-3 py-2 text-sm text-foreground/80" style={{ borderWidth: '1px', borderStyle: 'solid', borderColor: `rgb(var(${rgbVar}) / 0.15)` }} {...props}>{children}</td>
  ),
  tr: ({ children, ...props }: any) => (
    <tr className="even:bg-primary/3" {...props}>{children}</tr>
  ),
});

const baseCodeComponents = (rgbVar: string) => ({
  code: ({ className, children, ...props }: any) => {
    if (isMermaid(className)) {
      return <Mermaid chart={String(children).replace(/\n$/, "")} />;
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
  pre: ({ children, ...props }: any) => {
    const child: any = Array.isArray(children) ? children[0] : children;
    if (child?.props && isMermaid(child.props.className)) {
      return <>{children}</>;
    }
    if (child?.props) {
      const match = /language-(\S+)/.exec(child.props.className || "");
      const lang = match ? match[1].toLowerCase() : "text";
      const code = String(child.props.children).replace(/\n$/, "");
      return <CodeBlock code={code} lang={lang} />;
    }
    return <pre className="overflow-x-auto mb-4 text-sm" {...props}>{children}</pre>;
  },
});

export const markdownComponents = {
  h1: ({ children, ...props }: any) => (
    <h1 className="text-2xl font-bold mt-6 mb-4 first:mt-0 text-foreground" {...props}>{children}</h1>
  ),
  h2: ({ children, ...props }: any) => (
    <h2 className="text-xl font-bold mt-5 mb-3 first:mt-0 text-foreground" {...props}>{children}</h2>
  ),
  h3: ({ children, ...props }: any) => (
    <h3 className="text-lg font-bold mt-4 mb-2 first:mt-0 text-foreground" {...props}>{children}</h3>
  ),
  h4: ({ children, ...props }: any) => (
    <h4 className="text-base font-bold mt-3 mb-2 first:mt-0 text-foreground" {...props}>{children}</h4>
  ),
  p: ({ children, ...props }: any) => (
    <p className="mb-4 last:mb-0 text-foreground/90" {...props}>{children}</p>
  ),
  ul: ({ children, ...props }: any) => (
    <ul className="list-disc pl-6 mb-4 space-y-1" {...props}>{children}</ul>
  ),
  ol: ({ children, ...props }: any) => (
    <ol className="list-decimal pl-6 mb-4 space-y-1" {...props}>{children}</ol>
  ),
  li: ({ children, ...props }: any) => (
    <li {...props}>{children}</li>
  ),
  strong: ({ children, ...props }: any) => (
    <strong className="font-bold text-foreground" {...props}>{children}</strong>
  ),
  em: ({ children, ...props }: any) => (
    <em className="italic" {...props}>{children}</em>
  ),
  blockquote: ({ children, ...props }: any) => (
    <blockquote className="border-l-2 border-primary/40 pl-4 italic my-4" {...props}>{children}</blockquote>
  ),
  hr: ({ ...props }: any) => (
    <hr className="my-6 border-border" {...props} />
  ),
  a: ({ children, href, ...props }: any) => (
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

export const cyanMarkdownComponents = {
  ...baseCodeComponents("--cp-rgb-cyan"),
  ...baseTableComponents("--cp-rgb-cyan"),
};
