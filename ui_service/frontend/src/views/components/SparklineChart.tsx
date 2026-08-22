import { useId } from "react";

type SparklineChartProps = {
  values: number[];
  rising: boolean;
};

const WIDTH: number = 140;
const HEIGHT: number = 44;
const PADDING: number = 2;

export default function SparklineChart({
  values,
  rising,
}: SparklineChartProps): JSX.Element {
  const rawId: string = useId().replace(/:/g, "");
  const gradientId: string = `spark-${rawId}`;
  const stroke: string = rising ? "#4ade80" : "#f87171";

  if (values.length < 2) {
    return <div className="sparkline-empty">No data</div>;
  }

  const minValue: number = Math.min(...values);
  const maxValue: number = Math.max(...values);
  const range: number = maxValue - minValue || 1;
  const plotWidth: number = WIDTH - PADDING * 2;
  const plotHeight: number = HEIGHT - PADDING * 2;
  const points: Array<{ x: number; y: number }> = values.map(
    (value: number, index: number) => ({
      x: PADDING + (index / (values.length - 1)) * plotWidth,
      y: PADDING + (1 - (value - minValue) / range) * plotHeight,
    }),
  );
  const pathD: string = points
    .map(
      (point: { x: number; y: number }, index: number) =>
        `${index === 0 ? "M" : "L"} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`,
    )
    .join(" ");
  const areaD: string = [
    pathD,
    `L ${points[points.length - 1].x.toFixed(2)} ${(HEIGHT - PADDING).toFixed(2)}`,
    `L ${points[0].x.toFixed(2)} ${(HEIGHT - PADDING).toFixed(2)}`,
    "Z",
  ].join(" ");

  return (
    <svg
      className="sparkline-svg"
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      role="img"
      aria-hidden="true"
    >
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={stroke} stopOpacity="0.35" />
          <stop offset="100%" stopColor={stroke} stopOpacity="0.02" />
        </linearGradient>
      </defs>
      <path d={areaD} fill={`url(#${gradientId})`} />
      <path d={pathD} fill="none" stroke={stroke} strokeWidth="1.8" />
    </svg>
  );
}
