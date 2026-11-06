import { useRef, useEffect } from "react";
import { EditorState } from "@codemirror/state";
import { EditorView, keymap } from "@codemirror/view";
import { markdown } from "@codemirror/lang-markdown";
import { defaultKeymap } from "@codemirror/commands";
import { syntaxHighlighting, HighlightStyle } from "@codemirror/language";
import { tags } from "@lezer/highlight";
import { THEME, withAlpha } from "../lib/theme.ts";

const cyberpunkTheme = EditorView.theme(
  {
    "&": {
      backgroundColor: THEME.bg,
      color: THEME.text,
      height: "100%",
      fontSize: "13px",
    },
    ".cm-content": { caretColor: THEME.yellow, padding: "1rem 0" },
    ".cm-cursor, .cm-dropCursor": { borderLeftColor: THEME.yellow },
    "&.cm-focused .cm-selectionBackground, .cm-selectionBackground, .cm-content ::selection":
      { backgroundColor: withAlpha(THEME.yellow, 0.15) },
    ".cm-activeLine": { backgroundColor: withAlpha(THEME.yellow, 0.04) },
    ".cm-selectionMatch": { backgroundColor: withAlpha(THEME.cyan, 0.15) },
    ".cm-searchMatch": {
      backgroundColor: withAlpha(THEME.yellow, 0.2),
      outline: `1px solid ${withAlpha(THEME.yellow, 0.4)}`,
    },
    ".cm-searchMatch.cm-searchMatch-selected": {
      backgroundColor: withAlpha(THEME.yellow, 0.35),
    },
    "&.cm-focused .cm-matchingBracket, &.cm-focused .cm-nonmatchingBracket": {
      backgroundColor: withAlpha(THEME.yellow, 0.2),
      outline: `1px solid ${withAlpha(THEME.yellow, 0.5)}`,
    },
    ".cm-gutters": {
      backgroundColor: THEME.bg,
      color: THEME.warm,
      border: "none",
      borderRight: `1px solid ${withAlpha(THEME.yellow, 0.1)}`,
    },
    ".cm-activeLineGutter": {
      backgroundColor: withAlpha(THEME.yellow, 0.06),
      color: THEME.warmBright,
    },
    ".cm-foldPlaceholder": {
      backgroundColor: "transparent",
      border: "none",
      color: THEME.warm,
    },
    ".cm-tooltip": {
      backgroundColor: THEME.surface,
      border: `1px solid ${withAlpha(THEME.yellow, 0.2)}`,
      color: THEME.text,
    },
    ".cm-tooltip .cm-tooltip-arrow:before": {
      borderTopColor: withAlpha(THEME.yellow, 0.2),
      borderBottomColor: withAlpha(THEME.yellow, 0.2),
    },
    ".cm-tooltip .cm-tooltip-arrow:after": {
      borderTopColor: THEME.surface,
      borderBottomColor: THEME.surface,
    },
    ".cm-scroller": { overflow: "auto", padding: "0 1rem" },
  },
  { dark: true },
);

const cyberpunkHighlight = HighlightStyle.define([
  { tag: tags.heading1, color: THEME.yellow, fontWeight: "bold", fontSize: "1.4em" },
  { tag: tags.heading2, color: THEME.yellow, fontWeight: "bold", fontSize: "1.3em" },
  { tag: tags.heading3, color: THEME.yellow, fontWeight: "bold", fontSize: "1.2em" },
  { tag: tags.heading4, color: THEME.yellow, fontWeight: "bold", fontSize: "1.1em" },
  { tag: tags.heading5, color: THEME.yellow, fontWeight: "bold" },
  { tag: tags.heading6, color: THEME.yellow, fontWeight: "bold" },
  { tag: tags.strong, color: THEME.text, fontWeight: "bold" },
  { tag: tags.emphasis, color: THEME.warmBright, fontStyle: "italic" },
  { tag: tags.link, color: THEME.cyan },
  { tag: tags.url, color: THEME.cyan, textDecoration: "underline" },
  { tag: tags.monospace, color: THEME.cyan, backgroundColor: withAlpha(THEME.cyan, 0.08) },
  { tag: tags.quote, color: THEME.warm, fontStyle: "italic" },
  { tag: tags.comment, color: THEME.warm, fontStyle: "italic" },
  { tag: tags.keyword, color: THEME.red },
  { tag: tags.string, color: THEME.cyan },
  { tag: tags.number, color: THEME.cyan },
  { tag: tags.bool, color: THEME.red },
  { tag: tags.null, color: THEME.red },
  { tag: tags.operator, color: THEME.warmBright },
  { tag: tags.punctuation, color: THEME.warm },
  { tag: tags.bracket, color: THEME.warm },
  { tag: tags.atom, color: THEME.cyan },
  { tag: tags.meta, color: THEME.warmBright },
  { tag: tags.processingInstruction, color: THEME.warm },
  { tag: tags.strikethrough, textDecoration: "line-through", color: THEME.warm },
  { tag: tags.typeName, color: THEME.red },
  { tag: tags.tagName, color: THEME.cyan },
  { tag: tags.propertyName, color: THEME.warmBright },
]);

interface EditorProps {
  content: string;
  onContentChange: (content: string) => void;
  onSave: () => void;
}

export function Editor({ content, onContentChange, onSave }: EditorProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewRef = useRef<EditorView | null>(null);
  const onContentChangeRef = useRef(onContentChange);
  const onSaveRef = useRef(onSave);
  const initialContentRef = useRef(content);

  onContentChangeRef.current = onContentChange;
  onSaveRef.current = onSave;

  useEffect(() => {
    if (!containerRef.current) return;

    const state = EditorState.create({
      doc: initialContentRef.current,
      extensions: [
        markdown(),
        cyberpunkTheme,
        syntaxHighlighting(cyberpunkHighlight),
        keymap.of([
          ...defaultKeymap,
          {
            key: "Mod-s",
            run: () => {
              onSaveRef.current();
              return true;
            },
          },
        ]),
        EditorView.updateListener.of((update) => {
          if (update.docChanged) {
            onContentChangeRef.current(update.state.doc.toString());
          }
        }),
      ],
    });

    const view = new EditorView({
      state,
      parent: containerRef.current,
    });

    viewRef.current = view;

    return () => {
      view.destroy();
      viewRef.current = null;
    };
  }, []);

  return <div ref={containerRef} className="flex-1 overflow-hidden p-2" />;
}
