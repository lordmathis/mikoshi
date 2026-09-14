import type { CSSProperties, ReactNode } from "react";

export function CornerTriangle({
  position,
  color,
  size = 16,
  opacity = 0.4,
}: {
  position: "bl" | "tr";
  color: string;
  size?: number;
  opacity?: number;
}) {
  return (
    <div
      className={`absolute top-0 ${position === "bl" ? "right-0 cp-tri-bl" : "left-0 cp-tri-tr"}`}
      style={{ width: size, height: size, opacity, background: color }}
    />
  );
}

export function Scanlines() {
  return (
    <div
      className="absolute inset-0 pointer-events-none"
      style={{
        backgroundImage: `repeating-linear-gradient(0deg, transparent, transparent 3px, rgb(var(--cp-rgb-yellow) / 0.012) 3px, rgb(var(--cp-rgb-yellow) / 0.012) 4px)`,
      }}
    />
  );
}

export function MessageAvatar({
  icon,
  background,
}: {
  icon: ReactNode;
  background: CSSProperties["background"];
}) {
  return (
    <div className="flex-shrink-0 relative z-10">
      <div
        className="flex h-8 w-8 items-center justify-center cp-cut-8"
        style={{ background }}
      >
        {icon}
      </div>
    </div>
  );
}
