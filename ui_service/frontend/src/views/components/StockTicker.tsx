import {
  changeClassName,
  formatPercentChange,
  formatPrice,
} from "../../utils/formatters";
import type { MarketQuote } from "../../utils/marketPreviewData";

type StockTickerProps = {
  quotes: MarketQuote[];
};

type TickerItemsProps = {
  quotes: MarketQuote[];
  hidden: boolean;
};

function TickerItems({ quotes, hidden }: TickerItemsProps): JSX.Element {
  return (
    <ul className="ticker-list" aria-hidden={hidden || undefined}>
      {quotes.map((quote: MarketQuote) => (
        <li key={`${hidden ? "dup" : "live"}-${quote.symbol}`} className="ticker-item">
          <span className="ticker-symbol">{quote.symbol}</span>
          <span className="ticker-price">{formatPrice(quote.price)}</span>
          <span className={`ticker-change ${changeClassName(quote.percentChange)}`}>
            {formatPercentChange(quote.percentChange)}
          </span>
        </li>
      ))}
    </ul>
  );
}

export default function StockTicker({ quotes }: StockTickerProps): JSX.Element {
  return (
    <div className="ticker" aria-label="Market price runner">
      <div className="ticker-track">
        <TickerItems quotes={quotes} hidden={false} />
        <TickerItems quotes={quotes} hidden={true} />
      </div>
    </div>
  );
}
