import { useRef, useEffect } from "react";
import { EditorState } from "@codemirror/state";
import { EditorView, keymap } from "@codemirror/view";
import { markdown } from "@codemirror/lang-markdown";
import { defaultKeymap } from "@codemirror/commands";
import { syntaxHighlighting, HighlightStyle } from "@codemirror/language";
import { tags } from "@lezer/highlight";

const cyberpunkTheme = EditorView.theme(
  {
    "&": {
      backgroundColor: "#0a0a0c",
      color: "#f5f5f5",
      height: "100%",
      fontSize: "13px",
    },
    ".cm-content": { caretColor: "#f5d800", padding: "1rem 0" },
    ".cm-cursor, .cm-dropCursor": { borderLeftColor: "#f5d800" },
    "&.cm-focused .cm-selectionBackground, .cm-selectionBackground, .cm-content ::selection":
      { backgroundColor: "rgba(245, 216, 0, 0.15)" },
    ".cm-activeLine": { backgroundColor: "rgba(245, 216, 0, 0.04)" },
    ".cm-selectionMatch": { backgroundColor: "rgba(0, 212, 255, 0.15)" },
    ".cm-searchMatch": {
      backgroundColor: "rgba(245, 216, 0, 0.2)",
      outline: "1px solid rgba(245, 216, 0, 0.4)",
    },
    ".cm-searchMatch.cm-searchMatch-selected": {
      backgroundColor: "rgba(245, 216, 0, 0.35)",
    },
    "&.cm-focused .cm-matchingBracket, &.cm-focused .cm-nonmatchingBracket": {
      backgroundColor: "rgba(245, 216, 0, 0.2)",
      outline: "1px solid rgba(245, 216, 0, 0.5)",
    },
    ".cm-gutters": {
      backgroundColor: "#0a0a0c",
      color: "#a89e88",
      border: "none",
      borderRight: "1px solid rgba(245, 216, 0, 0.1)",
    },
    ".cm-activeLineGutter": {
      backgroundColor: "rgba(245, 216, 0, 0.06)",
      color: "#d0c8b0",
    },
    ".cm-foldPlaceholder": {
      backgroundColor: "transparent",
      border: "none",
      color: "#a89e88",
    },
    ".cm-tooltip": {
      backgroundColor: "#0f0f0f",
      border: "1px solid rgba(245, 216, 0, 0.2)",
      color: "#f5f5f5",
    },
    ".cm-tooltip .cm-tooltip-arrow:before": {
      borderTopColor: "rgba(245, 216, 0, 0.2)",
      borderBottomColor: "rgba(245, 216, 0, 0.2)",
    },
    ".cm-tooltip .cm-tooltip-arrow:after": {
      borderTopColor: "#0f0f0f",
      borderBottomColor: "#0f0f0f",
    },
    ".cm-scroller": { overflow: "auto", padding: "0 1rem" },
  },
  { dark: true },
);

const cyberpunkHighlight = HighlightStyle.define([
  { tag: tags.heading1, color: "#f5d800", fontWeight: "bold", fontSize: "1.4em" },
  { tag: tags.heading2, color: "#f5d800", fontWeight: "bold", fontSize: "1.3em" },
  { tag: tags.heading3, color: "#f5d800", fontWeight: "bold", fontSize: "1.2em" },
  { tag: tags.heading4, color: "#f5d800", fontWeight: "bold", fontSize: "1.1em" },
  { tag: tags.heading5, color: "#f5d800", fontWeight: "bold" },
  { tag: tags.heading6, color: "#f5d800", fontWeight: "bold" },
  { tag: tags.strong, color: "#f5f5f5", fontWeight: "bold" },
  { tag: tags.emphasis, color: "#d0c8b0", fontStyle: "italic" },
  { tag: tags.link, color: "#00d4ff" },
  { tag: tags.url, color: "#00d4ff", textDecoration: "underline" },
  { tag: tags.monospace, color: "#00d4ff", backgroundColor: "rgba(0, 212, 255, 0.08)" },
  { tag: tags.quote, color: "#a89e88", fontStyle: "italic" },
  { tag: tags.comment, color: "#a89e88", fontStyle: "italic" },
  { tag: tags.keyword, color: "#e63329" },
  { tag: tags.string, color: "#00d4ff" },
  { tag: tags.number, color: "#00d4ff" },
  { tag: tags.bool, color: "#e63329" },
  { tag: tags.null, color: "#e63329" },
  { tag: tags.operator, color: "#d0c8b0" },
  { tag: tags.punctuation, color: "#a89e88" },
  { tag: tags.bracket, color: "#a89e88" },
  { tag: tags.atom, color: "#00d4ff" },
  { tag: tags.meta, color: "#d0c8b0" },
  { tag: tags.processingInstruction, color: "#a89e88" },
  { tag: tags.strikethrough, textDecoration: "line-through", color: "#a89e88" },
  { tag: tags.list, color: "#f5d800" },
  { tag: tags.typeName, color: "#e63329" },
  { tag: tags.tagName, color: "#00d4ff" },
  { tag: tags.propertyName, color: "#d0c8b0" },
]);

interface FileEditorProps {
  content: string;
  onContentChange: (content: string) => void;
  onSave: () => void;
}

export function FileEditor({ content, onContentChange, onSave }: FileEditorProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewRef = useRef<EditorView | null>(null);
  const onContentChangeRef = useRef(onContentChange);
  const onSaveRef = useRef(onSave);

  onContentChangeRef.current = onContentChange;
  onSaveRef.current = onSave;

  useEffect(() => {
    if (!containerRef.current) return;

    const state = EditorState.create({
      doc: content,
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
