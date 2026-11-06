export const THEME = {
  bg: "#0a0a0c",
  surface: "#0f0f0f",
  surface2: "#141414",
  surface3: "#10100e",
  surface4: "#12110e",
  text: "#f5f5f5",
  textWarm: "#e8e0c8",
  warm: "#a89e88",
  warmBright: "#d0c8b0",
  yellow: "#f5d800",
  yellowDim: "#c4ac00",
  cyan: "#00d4ff",
  cyanBright: "#00f0ff",
  red: "#e63329",
  fontMono: "'Share Tech Mono', 'Courier New', monospace",
} as const;

export function withAlpha(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}
