import { formatPercentChange } from "../../utils/formatters";
import type { MarketQuote } from "../../utils/marketPreviewData";

type MarketBarChartProps = {
  quotes: MarketQuote[];
};

export default function MarketBarChart({
  quotes,
}: MarketBarChartProps): JSX.Element {
  const maxAbs: number = Math.max(
    0.5,
    ...quotes.map((quote: MarketQuote) => Math.abs(quote.percentChange)),
  );

  return (
    <ul className="market-bars">
      {quotes.map((quote: MarketQuote) => {
        const widthPct: number = (Math.abs(quote.percentChange) / maxAbs) * 50;
        const isUp: boolean = quote.percentChange >= 0;
        return (
          <li key={quote.symbol} className="market-bar-row">
            <span className="market-bar-symbol">{quote.symbol}</span>
            <div className="market-bar-track">
              <span className="market-bar-mid" />
              <span
                className={`market-bar-fill ${isUp ? "change-up" : "change-down"}`}
                style={{
                  width: `${widthPct}%`,
                  left: isUp ? "50%" : `${50 - widthPct}%`,
                }}
              />
            </div>
            <span className={isUp ? "change-up" : "change-down"}>
              {formatPercentChange(quote.percentChange)}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
