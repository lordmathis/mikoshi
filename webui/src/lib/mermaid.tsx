import { useEffect, useId, useState } from "react";
import { THEME } from "./theme.ts";

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

    void (async () => {
      try {
        const mermaid = (await import("mermaid")).default;
        if (!initialized) {
          mermaid.initialize({
            startOnLoad: false,
            theme: "base",
            fontFamily: THEME.fontMono,
            themeVariables: {
              background: THEME.bg,
              primaryColor: THEME.surface2,
              primaryTextColor: THEME.text,
              primaryBorderColor: THEME.yellow,
              secondaryColor: THEME.surface3,
              secondaryTextColor: THEME.warmBright,
              secondaryBorderColor: THEME.cyan,
              tertiaryColor: THEME.surface4,
              tertiaryTextColor: THEME.warm,
              tertiaryBorderColor: THEME.red,
              lineColor: THEME.cyan,
              textColor: THEME.text,
              edgeLabelBackground: THEME.surface,
              clusterBkg: THEME.surface3,
              clusterBorder: THEME.yellow,
              labelColor: THEME.text,
              nodeTextColor: THEME.text,
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
      <div className="mb-4 flex justify-center py-6 text-xs text-foreground/70 uppercase tracking-widest">
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
