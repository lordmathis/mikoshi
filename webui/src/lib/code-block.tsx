import { useEffect, useRef, useState } from "react";
import { Check, Copy } from "lucide-react";
import { createHighlighterCore, type HighlighterCore, type LanguageRegistration, type ThemeRegistration } from "shiki/core";
import { createOnigurumaEngine } from "shiki/engine/oniguruma";
import { THEME } from "./theme.ts";

const theme: ThemeRegistration = {
  name: "mikoshi-dark",
  type: "dark",
  bg: "transparent",
  fg: THEME.text,
  settings: [
    {
      scope: ["comment", "punctuation.definition.comment", "string.comment", "markup.quote"],
      settings: { foreground: THEME.warm, fontStyle: "italic" },
    },
    {
      scope: ["string", "string.template", "meta.embedded"],
      settings: { foreground: THEME.cyan },
    },
    {
      scope: ["constant.character.escape"],
      settings: { foreground: THEME.cyanBright },
    },
    {
      scope: [
        "constant.numeric",
        "constant.language",
        "constant.other.symbol",
        "variable.other.constant",
      ],
      settings: { foreground: THEME.textWarm },
    },
    {
      scope: [
        "keyword",
        "keyword.control",
        "keyword.control.import",
        "storage",
        "storage.modifier",
      ],
      settings: { foreground: THEME.yellow },
    },
    {
      scope: [
        "entity.name.type",
        "support.type",
        "support.class",
        "entity.other.inherited-class",
      ],
      settings: { foreground: THEME.yellowDim },
    },
    {
      scope: [
        "entity.name.function",
        "support.function",
        "meta.function-call",
        "variable.function",
      ],
      settings: { foreground: THEME.cyanBright },
    },
    {
      scope: [
        "variable.other.property",
        "variable.other.object.property",
        "meta.property-name",
        "support.type.property-name",
        "meta.object-literal.key",
        "entity.other.attribute-name",
      ],
      settings: { foreground: THEME.warmBright },
    },
    {
      scope: ["entity.name.tag"],
      settings: { foreground: THEME.yellow },
    },
    {
      scope: [
        "punctuation.definition",
        "punctuation.separator",
        "punctuation.terminator",
        "keyword.operator",
      ],
      settings: { foreground: THEME.warmBright },
    },
    {
      scope: ["meta.decorator", "punctuation.decorator", "string.regexp"],
      settings: { foreground: THEME.red },
    },
    {
      scope: ["invalid", "invalid.illegal"],
      settings: { foreground: THEME.red },
    },
    {
      scope: ["markup.heading", "entity.name.section"],
      settings: { foreground: THEME.yellow, fontStyle: "bold" },
    },
    {
      scope: ["string.other.link.title", "markup.underline.link"],
      settings: { foreground: THEME.cyanBright },
    },
    {
      scope: ["markup.inserted.diff", "markup.inserted"],
      settings: { foreground: THEME.cyan },
    },
    {
      scope: ["markup.deleted.diff", "markup.deleted"],
      settings: { foreground: THEME.red },
    },
    {
      scope: ["meta.diff.range", "meta.diff.header"],
      settings: { foreground: THEME.yellow },
    },
  ],
};

const ts = () => import("shiki/langs/typescript.mjs");
const js = () => import("shiki/langs/javascript.mjs");
const bash = () => import("shiki/langs/bash.mjs");
const md = () => import("shiki/langs/markdown.mjs");
const py = () => import("shiki/langs/python.mjs");
const json = () => import("shiki/langs/json.mjs");
const html = () => import("shiki/langs/html.mjs");
const yaml = () => import("shiki/langs/yaml.mjs");
const diff = () => import("shiki/langs/diff.mjs");

const LANGS: Record<string, () => Promise<{ default: LanguageRegistration | LanguageRegistration[] }>> = {
  typescript: ts, ts: ts,
  javascript: js, js: js,
  tsx: () => import("shiki/langs/tsx.mjs"),
  jsx: () => import("shiki/langs/jsx.mjs"),
  bash, sh: bash, shell: bash, zsh: bash,
  markdown: md, md: md,
  python: py, py: py,
  json, jsonc: json,
  yaml, yml: yaml,
  toml: () => import("shiki/langs/toml.mjs"),
  ini: () => import("shiki/langs/ini.mjs"),
  diff,
  css: () => import("shiki/langs/css.mjs"),
  scss: () => import("shiki/langs/scss.mjs"),
  html,
  xml: () => import("shiki/langs/xml.mjs"),
  sql: () => import("shiki/langs/sql.mjs"),
  go: () => import("shiki/langs/go.mjs"),
  rust: () => import("shiki/langs/rust.mjs"),
  c: () => import("shiki/langs/c.mjs"),
  cpp: () => import("shiki/langs/cpp.mjs"),
  lua: () => import("shiki/langs/lua.mjs"),
  dockerfile: () => import("shiki/langs/dockerfile.mjs"),
  docker: () => import("shiki/langs/docker.mjs"),
  hcl: () => import("shiki/langs/hcl.mjs"),
  terraform: () => import("shiki/langs/terraform.mjs"),
  nginx: () => import("shiki/langs/nginx.mjs"),
  makefile: () => import("shiki/langs/makefile.mjs"),
  graphql: () => import("shiki/langs/graphql.mjs"),
};

const CORE_LANGS = [ts(), js(), bash(), py(), json(), yaml(), diff(), md()];

let highlighterPromise: Promise<HighlighterCore> | null = null;

function getHighlighter(): Promise<HighlighterCore> {
  if (!highlighterPromise) {
    highlighterPromise = createHighlighterCore({
      themes: [theme],
      langs: CORE_LANGS,
      engine: createOnigurumaEngine(import("shiki/wasm")),
    });
  }
  return highlighterPromise;
}

async function resolveLang(lang: string): Promise<string> {
  if (!lang) return "text";
  const loader = LANGS[lang];
  if (!loader) return "text";
  const highlighter = await getHighlighter();
  if (!highlighter.getLoadedLanguages().includes(lang)) {
    await highlighter.loadLanguage(loader());
  }
  return lang;
}

interface CodeBlockProps {
  code: string;
  lang: string;
}

export function CodeBlock({ code, lang }: CodeBlockProps) {
  const [html, setHtml] = useState("");
  const [error, setError] = useState(false);
  const [copied, setCopied] = useState(false);
  const copyTimer = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => {
    let cancelled = false;

    void (async () => {
      try {
        const highlighter = await getHighlighter();
        const resolved = await resolveLang(lang);
        const result = highlighter.codeToHtml(code, { lang: resolved, theme: "mikoshi-dark" });
        if (!cancelled) {
          setHtml(result);
          setError(false);
        }
      } catch {
        if (!cancelled) {
          setError(true);
          setHtml("");
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [code, lang]);

  useEffect(() => () => clearTimeout(copyTimer.current), []);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      clearTimeout(copyTimer.current);
      copyTimer.current = setTimeout(() => setCopied(false), 2000);
    } catch {}
  };

  return (
    <div className="group relative mb-4 border border-border bg-cp-surface leading-relaxed">
      {html ? (
        <div className="overflow-x-auto p-3 text-sm" dangerouslySetInnerHTML={{ __html: html }} />
      ) : error ? (
        <pre className="overflow-x-auto p-3 text-sm">{code}</pre>
      ) : (
        <div className="flex justify-center py-4 text-xs text-foreground/70 uppercase tracking-widest">
          Highlighting...
        </div>
      )}
      <button
        onClick={() => void handleCopy()}
        aria-label="Copy code"
        className="absolute right-2 top-2 p-1.5 cp-cut-6 border border-border bg-cp-surface2 text-foreground/70 opacity-0 group-hover:opacity-100 transition hover:text-primary hover:border-primary/40"
      >
        {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
      </button>
    </div>
  );
}
