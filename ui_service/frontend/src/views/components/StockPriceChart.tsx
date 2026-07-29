import { useRef, useState } from "react";
import type { MouseEvent as ReactMouseEvent } from "react";

import type { StockHistoryBar } from "../../models/stocks";
import { formatPrice } from "../../utils/formatters";

type StockPriceChartProps = {
  bars: StockHistoryBar[];
};

type Point = {
  x: number;
  y: number;
  date: string;
  close: number;
};

const WIDTH: number = 800;
const HEIGHT: number = 280;
const PADDING: { top: number; right: number; bottom: number; left: number } = {
  top: 16,
  right: 16,
  bottom: 36,
  left: 56,
};

function buildPoints(bars: StockHistoryBar[]): Point[] {
  const usable: Array<{ date: string; close: number }> = bars
    .filter(
      (bar: StockHistoryBar) =>
        bar.close !== null &&
        bar.close !== undefined &&
        !Number.isNaN(Number(bar.close)),
    )
    .map((bar: StockHistoryBar) => ({
      date: bar.date,
      close: Number(bar.close),
    }));

  if (usable.length === 0) {
    return [];
  }

  const closes: number[] = usable.map((item) => item.close);
  const minClose: number = Math.min(...closes);
  const maxClose: number = Math.max(...closes);
  const range: number = maxClose - minClose || 1;
  const plotWidth: number = WIDTH - PADDING.left - PADDING.right;
  const plotHeight: number = HEIGHT - PADDING.top - PADDING.bottom;

  return usable.map((item, index: number) => {
    const xRatio: number =
      usable.length === 1 ? 0.5 : index / (usable.length - 1);
    const yRatio: number = (item.close - minClose) / range;
    return {
      x: PADDING.left + xRatio * plotWidth,
      y: PADDING.top + (1 - yRatio) * plotHeight,
      date: item.date,
      close: item.close,
    };
  });
}

function formatAxisPrice(value: number): string {
  return value.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function findNearestPoint(points: Point[], svgX: number): Point {
  let nearest: Point = points[0];
  let bestDistance: number = Math.abs(points[0].x - svgX);
  for (let index = 1; index < points.length; index += 1) {
    const distance: number = Math.abs(points[index].x - svgX);
    if (distance < bestDistance) {
      bestDistance = distance;
      nearest = points[index];
    }
  }
  return nearest;
}

export default function StockPriceChart({
  bars,
}: StockPriceChartProps): JSX.Element {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [hoverPoint, setHoverPoint] = useState<Point | null>(null);
  const points: Point[] = buildPoints(bars);

  if (points.length === 0) {
    return (
      <div className="stock-chart-empty">No historical price data available.</div>
    );
  }

  const closes: number[] = points.map((point: Point) => point.close);
  const minClose: number = Math.min(...closes);
  const maxClose: number = Math.max(...closes);
  const midClose: number = (minClose + maxClose) / 2;
  const pathD: string = points
    .map((point: Point, index: number) =>
      `${index === 0 ? "M" : "L"} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`,
    )
    .join(" ");
  const areaD: string = [
    pathD,
    `L ${points[points.length - 1].x.toFixed(2)} ${(HEIGHT - PADDING.bottom).toFixed(2)}`,
    `L ${points[0].x.toFixed(2)} ${(HEIGHT - PADDING.bottom).toFixed(2)}`,
    "Z",
  ].join(" ");
  const firstDate: string = points[0].date;
  const lastDate: string = points[points.length - 1].date;
  const midDate: string = points[Math.floor(points.length / 2)].date;

  function handleMouseMove(event: ReactMouseEvent<SVGSVGElement>): void {
    const svg: SVGSVGElement | null = svgRef.current;
    if (!svg) {
      return;
    }
    const rect: DOMRect = svg.getBoundingClientRect();
    if (rect.width <= 0) {
      return;
    }
    const svgX: number = ((event.clientX - rect.left) / rect.width) * WIDTH;
    if (svgX < PADDING.left || svgX > WIDTH - PADDING.right) {
      setHoverPoint(null);
      return;
    }
    setHoverPoint(findNearestPoint(points, svgX));
  }

  function handleMouseLeave(): void {
    setHoverPoint(null);
  }

  const tooltipOnRight: boolean =
    hoverPoint !== null && hoverPoint.x < WIDTH / 2;
  const tooltipX: number = hoverPoint
    ? hoverPoint.x + (tooltipOnRight ? 12 : -12)
    : 0;
  const tooltipY: number = hoverPoint
    ? Math.max(PADDING.top + 8, hoverPoint.y - 28)
    : 0;

  return (
    <div className="stock-chart-wrap">
      <svg
        ref={svgRef}
        className="stock-chart-svg"
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label="Stock price history chart"
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
      >
        <defs>
          <linearGradient id="stock-chart-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.35" />
            <stop offset="100%" stopColor="#38bdf8" stopOpacity="0.02" />
          </linearGradient>
        </defs>
        <line
          className="stock-chart-grid"
          x1={PADDING.left}
          y1={PADDING.top}
          x2={WIDTH - PADDING.right}
          y2={PADDING.top}
        />
        <line
          className="stock-chart-grid"
          x1={PADDING.left}
          y1={HEIGHT / 2}
          x2={WIDTH - PADDING.right}
          y2={HEIGHT / 2}
        />
        <line
          className="stock-chart-grid"
          x1={PADDING.left}
          y1={HEIGHT - PADDING.bottom}
          x2={WIDTH - PADDING.right}
          y2={HEIGHT - PADDING.bottom}
        />
        <path d={areaD} fill="url(#stock-chart-fill)" />
        <path d={pathD} className="stock-chart-line" fill="none" />
        <text
          className="stock-chart-axis"
          x={PADDING.left - 8}
          y={PADDING.top + 4}
          textAnchor="end"
        >
          {formatAxisPrice(maxClose)}
        </text>
        <text
          className="stock-chart-axis"
          x={PADDING.left - 8}
          y={HEIGHT / 2 + 4}
          textAnchor="end"
        >
          {formatAxisPrice(midClose)}
        </text>
        <text
          className="stock-chart-axis"
          x={PADDING.left - 8}
          y={HEIGHT - PADDING.bottom}
          textAnchor="end"
        >
          {formatAxisPrice(minClose)}
        </text>
        <text
          className="stock-chart-axis"
          x={PADDING.left}
          y={HEIGHT - 10}
          textAnchor="start"
        >
          {firstDate}
        </text>
        <text
          className="stock-chart-axis"
          x={WIDTH / 2}
          y={HEIGHT - 10}
          textAnchor="middle"
        >
          {midDate}
        </text>
        <text
          className="stock-chart-axis"
          x={WIDTH - PADDING.right}
          y={HEIGHT - 10}
          textAnchor="end"
        >
          {lastDate}
        </text>
        {hoverPoint ? (
          <g className="stock-chart-hover">
            <line
              className="stock-chart-crosshair"
              x1={hoverPoint.x}
              y1={PADDING.top}
              x2={hoverPoint.x}
              y2={HEIGHT - PADDING.bottom}
            />
            <circle
              className="stock-chart-hover-dot"
              cx={hoverPoint.x}
              cy={hoverPoint.y}
              r={4.5}
            />
            <g
              transform={`translate(${tooltipX}, ${tooltipY})`}
              textAnchor={tooltipOnRight ? "start" : "end"}
            >
              <rect
                className="stock-chart-tooltip-bg"
                x={tooltipOnRight ? -8 : -112}
                y={-18}
                width={120}
                height={40}
                rx={6}
              />
              <text className="stock-chart-tooltip-date" x={0} y={-2}>
                {hoverPoint.date}
              </text>
              <text className="stock-chart-tooltip-price" x={0} y={16}>
                {formatPrice(hoverPoint.close)}
              </text>
            </g>
          </g>
        ) : null}
      </svg>
    </div>
  );
}
