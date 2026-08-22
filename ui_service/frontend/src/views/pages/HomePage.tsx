import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import type { StockHistoryBar } from "../../models/stocks";
import {
  changeClassName,
  formatPercentChange,
  formatPrice,
} from "../../utils/formatters";
import {
  FEATURED_SYMBOLS,
  seriesToHistoryBars,
  type MarketQuote,
} from "../../utils/marketPreviewData";
import { useMarketQuotes } from "../../utils/useMarketQuotes";
import HomeNav from "../components/HomeNav";
import MarketBarChart from "../components/MarketBarChart";
import SparklineChart from "../components/SparklineChart";
import StockPriceChart from "../components/StockPriceChart";
import StockTicker from "../components/StockTicker";

export default function HomePage(): JSX.Element {
  const quotes: MarketQuote[] = useMarketQuotes();
  const [selectedSymbol, setSelectedSymbol] = useState<string>(FEATURED_SYMBOLS[0]);

  const featuredQuotes: MarketQuote[] = useMemo(
    () =>
      FEATURED_SYMBOLS.map(
        (symbol: string) => quotes.find((quote: MarketQuote) => quote.symbol === symbol),
      ).filter((quote: MarketQuote | undefined): quote is MarketQuote => Boolean(quote)),
    [quotes],
  );

  const selectedQuote: MarketQuote | undefined =
    featuredQuotes.find((quote: MarketQuote) => quote.symbol === selectedSymbol) ??
    featuredQuotes[0];

  const selectedBars: StockHistoryBar[] = useMemo(
    () => (selectedQuote ? seriesToHistoryBars(selectedQuote.series) : []),
    [selectedQuote],
  );

  return (
    <div className="home-page">
      <HomeNav />
      <StockTicker quotes={quotes} />

      <main className="home-hero">
        <div className="home-hero-content">
          <h1>
            Track your investments
            <br />
            with confidence
          </h1>
          <p>
            Monitor live-looking market data, build your portfolio, and get
            AI-powered insights — all in one place.
          </p>
          <div className="home-hero-actions">
            <Link to="/register" className="btn-solid btn-large">
              Get started
            </Link>
            <Link to="/login" className="btn-outline btn-large">
              Log in
            </Link>
          </div>
        </div>

        <section className="home-market" aria-label="Interactive market snapshot">
          <div className="home-market-chart dashboard-panel">
            <div className="stock-chart-header">
              <div>
                <p className="home-market-kicker">Featured chart</p>
                <h2>
                  {selectedQuote ? selectedQuote.name : "Market"}{" "}
                  <span className="stock-summary-symbol">
                    {selectedQuote ? selectedQuote.symbol : ""}
                  </span>
                </h2>
              </div>
              {selectedQuote ? (
                <div className="home-market-price">
                  <span className="stock-summary-price home-market-price-value">
                    {formatPrice(selectedQuote.price)}
                  </span>
                  <span className={changeClassName(selectedQuote.percentChange)}>
                    {formatPercentChange(selectedQuote.percentChange)}
                  </span>
                </div>
              ) : null}
            </div>
            <div className="stock-range-selectors home-market-tabs">
              {featuredQuotes.map((quote: MarketQuote) => (
                <button
                  key={quote.symbol}
                  type="button"
                  className={
                    quote.symbol === selectedQuote?.symbol
                      ? "stock-range-btn stock-range-btn-active"
                      : "stock-range-btn"
                  }
                  onClick={() => setSelectedSymbol(quote.symbol)}
                >
                  {quote.symbol}
                </button>
              ))}
            </div>
            {selectedQuote ? <StockPriceChart bars={selectedBars} /> : null}
          </div>

          <div className="home-spark-grid">
            {featuredQuotes.map((quote: MarketQuote) => (
              <button
                key={quote.symbol}
                type="button"
                className={
                  quote.symbol === selectedQuote?.symbol
                    ? "home-spark-card home-spark-card-active"
                    : "home-spark-card"
                }
                onClick={() => setSelectedSymbol(quote.symbol)}
              >
                <div className="home-spark-meta">
                  <span className="ticker-symbol">{quote.symbol}</span>
                  <span className={changeClassName(quote.percentChange)}>
                    {formatPercentChange(quote.percentChange)}
                  </span>
                </div>
                <span className="home-spark-name">{quote.name}</span>
                <span className="ticker-price">{formatPrice(quote.price)}</span>
                <SparklineChart
                  values={quote.series}
                  rising={quote.percentChange >= 0}
                />
              </button>
            ))}
          </div>
        </section>

        <section className="home-movers dashboard-panel" aria-label="Session movers">
          <div className="stock-chart-header">
            <div>
              <p className="home-market-kicker">Session movers</p>
              <h2>Percent change across the tape</h2>
            </div>
          </div>
          <MarketBarChart quotes={quotes} />
        </section>

        <div className="home-features">
          <div className="feature-card">
            <h3>Real-time Data</h3>
            <p>
              Live stock prices, indices, and crypto updated throughout the
              trading day.
            </p>
          </div>
          <div className="feature-card">
            <h3>Portfolio Tracking</h3>
            <p>
              Build and manage your personal portfolio with detailed performance
              metrics.
            </p>
          </div>
          <div className="feature-card">
            <h3>AI Insights</h3>
            <p>
              Get smart analysis and recommendations powered by artificial
              intelligence.
            </p>
          </div>
        </div>
      </main>

      <footer className="home-footer">
        <p>Stock Tracker &mdash; Your personal investment companion</p>
        <p className="home-footer-note">
          Home-page quotes are an illustrative snapshot, not live brokerage data.
        </p>
      </footer>
    </div>
  );
}
