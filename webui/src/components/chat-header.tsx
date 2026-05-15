import { Button } from "./ui/button";

interface ChatHeaderProps {
  sidebarOpen: boolean;
  onToggleSidebar: () => void;
  chatTitle?: string;
}

export function ChatHeader({ sidebarOpen, onToggleSidebar, chatTitle }: ChatHeaderProps) {
  return (
    <div
      className="sticky top-0 z-20 shrink-0 px-4 py-3 sm:px-6 overflow-hidden"
      style={{
        background: "linear-gradient(180deg, rgb(var(--cp-rgb-surface3) / 0.95) 0%, rgb(var(--cp-rgb-surface3) / 0.8) 100%)",
        backdropFilter: "blur(8px)",
        borderBottom: "1px solid rgb(var(--cp-rgb-yellow) / 0.15)",
      }}
    >
      <div className="flex items-center gap-3">
        {!sidebarOpen && (
          <Button
            variant="ghost"
            size="icon"
            onClick={onToggleSidebar}
            className="h-8 w-8 shrink-0"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <rect width="18" height="18" x="3" y="3" />
              <path d="M9 3v18" />
            </svg>
            <span className="sr-only">Open sidebar</span>
          </Button>
        )}
        <div className="flex flex-col min-w-0 flex-1">
          <h1
            className="text-sm font-bold text-primary uppercase tracking-[0.15em]"
            style={{ fontFamily: 'var(--font-mono)', fontSize: '16px' }}
          >
            Mikoshi
          </h1>
          {chatTitle && (
            <p className="cp-label text-muted-foreground truncate mt-0.5">
              {chatTitle}
            </p>
          )}
        </div>
        <div className="flex items-center gap-1.5" style={{ animation: 'cp-status-glow 2s ease-in-out infinite' }}>
          <div className="relative w-2.5 h-2.5">
            <div className="absolute inset-0 bg-cp-cyan-bright cp-diamond" />
            <div className="absolute inset-0 bg-cp-cyan-bright cp-diamond" style={{ animation: 'cp-blink 1.5s ease-in-out infinite' }} />
          </div>
          <span className="cp-label text-cp-cyan-bright/70">SYS</span>
          <span className="cp-label text-cp-cyan-bright/40">:</span>
          <span className="cp-label text-cp-cyan-bright/70">OK</span>
        </div>
      </div>
      <div className="h-[2px] mt-2 bg-gradient-to-r from-primary/40 via-primary/10 to-transparent" />
    </div>
  );
}
