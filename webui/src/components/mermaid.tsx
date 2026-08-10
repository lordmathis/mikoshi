import { useEffect, useId, useState } from "react";

interface MermaidProps {
  chart: string;
}

let initialized = false;

export function Mermaid({ chart }: MermaidProps) {
  const rawId = useId();
  const id = `mermaid-${rawId.replace(/[^a-zA-Z0-9]/g, "")}`;
  const [svg, setSvg] = useState<string>("");
  const [error, setError] = useState<string>("");

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const mermaid = (await import("mermaid")).default;
        if (!initialized) {
          mermaid.initialize({
            startOnLoad: false,
            theme: "base",
            fontFamily: "'Share Tech Mono', 'Courier New', monospace",
            themeVariables: {
              background: "#0a0a0c",
              primaryColor: "#141414",
              primaryTextColor: "#f5f5f5",
              primaryBorderColor: "#f5d800",
              secondaryColor: "#10100e",
              secondaryTextColor: "#d0c8b0",
              secondaryBorderColor: "#00d4ff",
              tertiaryColor: "#12110e",
              tertiaryTextColor: "#a89e88",
              tertiaryBorderColor: "#e63329",
              lineColor: "#00d4ff",
              textColor: "#f5f5f5",
              edgeLabelBackground: "#0f0f0f",
              clusterBkg: "#10100e",
              clusterBorder: "#f5d800",
              labelColor: "#f5f5f5",
              nodeTextColor: "#f5f5f5",
              fontSize: "14px",
            },
          });
          initialized = true;
        }

        const result = await mermaid.render(id, chart);
        if (!cancelled) {
          setSvg(result.svg);
          setError("");
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err));
          setSvg("");
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [chart, id]);

  if (error) {
    return (
      <pre className="overflow-x-auto mb-4 p-3 text-xs text-[var(--color-cp-red)] bg-cp-surface2 border border-[var(--color-cp-red)]/30">
        <code>{error}</code>
      </pre>
    );
  }

  if (!svg) {
    return (
      <div className="mb-4 flex justify-center py-6 text-xs text-[var(--color-cp-text-muted)] uppercase tracking-widest">
        Rendering diagram...
      </div>
    );
  }

  return (
    <div
      className="mb-4 flex justify-center overflow-x-auto"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}
