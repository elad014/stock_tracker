const MARK_COLORS: readonly string[] = [
  "#38bdf8",
  "#a78bfa",
  "#f472b6",
  "#fb923c",
  "#4ade80",
  "#facc15",
  "#2dd4bf",
  "#f87171",
  "#818cf8",
  "#e879f9",
  "#34d399",
  "#fbbf24",
];

export function markColorForIndex(index: number): string {
  const safeIndex = ((index % MARK_COLORS.length) + MARK_COLORS.length) % MARK_COLORS.length;
  return MARK_COLORS[safeIndex];
}

type StockMarkProps = {
  symbol: string;
  color: string;
};

export default function StockMark({ symbol, color }: StockMarkProps): JSX.Element {
  const label = symbol.trim().toUpperCase();
  return (
    <span className="stock-mark" style={{ backgroundColor: color }} aria-hidden="true">
      {label.slice(0, 1)}
    </span>
  );
}
