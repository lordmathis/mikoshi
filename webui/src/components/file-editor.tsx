import { useRef, useEffect } from "react";
import { EditorState } from "@codemirror/state";
import { EditorView, keymap } from "@codemirror/view";
import { markdown } from "@codemirror/lang-markdown";
import { oneDark } from "@codemirror/theme-one-dark";
import { defaultKeymap } from "@codemirror/commands";

interface FileEditorProps {
  content: string;
  onContentChange: (content: string) => void;
  onSave: () => void;
}

export function FileEditor({ content, onContentChange, onSave }: FileEditorProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewRef = useRef<EditorView | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const state = EditorState.create({
      doc: content,
      extensions: [
        markdown(),
        oneDark,
        keymap.of([
          ...defaultKeymap,
          {
            key: "Mod-s",
            run: () => {
              onSave();
              return true;
            },
          },
        ]),
        EditorView.updateListener.of((update) => {
          if (update.docChanged) {
            onContentChange(update.state.doc.toString());
          }
        }),
        EditorView.theme({
          "&": {
            height: "100%",
            fontSize: "13px",
          },
          ".cm-scroller": {
            overflow: "auto",
            padding: "0 1rem",
          },
          ".cm-content": {
            padding: "1rem 0",
          },
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

  return <div ref={containerRef} className="flex-1 overflow-hidden" />;
}
