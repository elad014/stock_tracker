import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import {
  changeClassName,
  formatPercentChange,
  formatPrice,
} from "../../utils/formatters";
import type { MarketQuote } from "../../utils/marketPreviewData";
import { useMarketQuotes } from "../../utils/useMarketQuotes";
import HomeNav from "./HomeNav";
import SparklineChart from "./SparklineChart";
import StockTicker from "./StockTicker";

type AuthLayoutProps = {
  title: string;
  subtitle?: string;
  children: ReactNode;
};

export default function AuthLayout({
  title,
  subtitle,
  children,
}: AuthLayoutProps): JSX.Element {
  const quotes: MarketQuote[] = useMarketQuotes();
  const previewQuotes: MarketQuote[] = quotes.slice(0, 4);

  return (
    <div className="auth-page">
      <HomeNav />
      <StockTicker quotes={quotes} />
      <div className="auth-shell">
        <div className="auth-card">
          <h1>{title}</h1>
          {subtitle ? <p className="subtitle">{subtitle}</p> : null}
          {children}
        </div>
        <aside className="auth-aside">
          <p className="auth-aside-kicker">Market snapshot</p>
          <h2>Follow prices, charts, and news in one place</h2>
          <p className="auth-aside-copy">
            Sign in to build a watchlist, inspect history, and get AI summaries
            on the names you track.
          </p>
          <ul className="auth-aside-quotes">
            {previewQuotes.map((quote: MarketQuote) => (
              <li key={quote.symbol} className="auth-aside-quote">
                <div className="auth-aside-quote-meta">
                  <span className="ticker-symbol">{quote.symbol}</span>
                  <span className="ticker-price">{formatPrice(quote.price)}</span>
                  <span className={changeClassName(quote.percentChange)}>
                    {formatPercentChange(quote.percentChange)}
                  </span>
                </div>
                <SparklineChart
                  values={quote.series}
                  rising={quote.percentChange >= 0}
                />
              </li>
            ))}
          </ul>
          <Link to="/" className="btn-outline auth-aside-link">
            Back to home
          </Link>
        </aside>
      </div>
    </div>
  );
}
