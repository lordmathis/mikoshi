import remarkGfm from "remark-gfm";
import remarkBreaks from "remark-breaks";
import rehypeHighlight from "rehype-highlight";

export const REMARK_PLUGINS: any[] = [remarkGfm, remarkBreaks];
export const REHYPE_PLUGINS: any[] = [rehypeHighlight];

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
  code: ({ inline, className, children, ...props }: any) => {
    return inline ? (
      <code className="bg-primary/[0.08] px-1.5 py-0.5 text-xs text-primary/90" {...props}>
        {children}
      </code>
    ) : (
      <code className={className} {...props}>
        {children}
      </code>
    );
  },
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
  ...baseTableComponents("--cp-rgb-yellow"),
};

export const cyanMarkdownComponents = {
  ...baseTableComponents("--cp-rgb-cyan"),
};
