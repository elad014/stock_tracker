import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import type { HistoryRange, StockDetails, StockHistoryBar } from "../../models/stocks";
import { fetchStockDetails, fetchStockHistory } from "../../services/stockService";
import {
  changeClassName,
  formatChange,
  formatPercentChange,
  formatPrice,
  formatVolume,
} from "../../utils/formatters";
import StockNewsArticles from "../components/StockNewsArticles";
import StockPriceChart from "../components/StockPriceChart";

const HISTORY_RANGES: HistoryRange[] = ["1D", "5D", "1M", "3M", "6M", "1Y", "5Y"];

function formatApiError(err: unknown, fallback: string): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response
    ?.data?.detail;
  if (typeof detail === "string") {
    return detail;
  }
  return fallback;
}

export default function StockDetailsPage(): JSX.Element {
  const navigate = useNavigate();
  const { stockId } = useParams<{ stockId: string }>();
  const [stock, setStock] = useState<StockDetails | null>(null);
  const [history, setHistory] = useState<StockHistoryBar[]>([]);
  const [range, setRange] = useState<HistoryRange>("1Y");
  const [loadingStock, setLoadingStock] = useState<boolean>(true);
  const [loadingHistory, setLoadingHistory] = useState<boolean>(true);
  const [stockError, setStockError] = useState<string>("");
  const [historyError, setHistoryError] = useState<string>("");

  useEffect(() => {
    if (!stockId) {
      setStockError("Stock not found");
      setLoadingStock(false);
      return;
    }

    let cancelled: boolean = false;

    async function loadStock(): Promise<void> {
      setLoadingStock(true);
      setStockError("");
      setStock(null);
      try {
        const data: StockDetails = await fetchStockDetails(stockId as string);
        if (!cancelled) {
          setStock(data);
        }
      } catch (err: unknown) {
        if (cancelled) {
          return;
        }
        const status: number | undefined = (
          err as { response?: { status?: number } }
        ).response?.status;
        if (status === 401) {
          localStorage.removeItem("access_token");
          navigate("/login");
          return;
        }
        if (status === 404) {
          setStockError("Stock not found");
        } else {
          setStockError(formatApiError(err, "Failed to load stock details"));
        }
      } finally {
        if (!cancelled) {
          setLoadingStock(false);
        }
      }
    }

    void loadStock();
    return () => {
      cancelled = true;
    };
  }, [stockId, navigate]);

  useEffect(() => {
    if (!stockId) {
      setLoadingHistory(false);
      return;
    }

    let cancelled: boolean = false;

    async function loadHistory(): Promise<void> {
      setLoadingHistory(true);
      setHistoryError("");
      try {
        const data: StockHistoryBar[] = await fetchStockHistory(
          stockId as string,
          range,
        );
        if (!cancelled) {
          setHistory(data);
        }
      } catch (err: unknown) {
        if (cancelled) {
          return;
        }
        const status: number | undefined = (
          err as { response?: { status?: number } }
        ).response?.status;
        if (status === 401) {
          localStorage.removeItem("access_token");
          navigate("/login");
          return;
        }
        setHistory([]);
        setHistoryError(formatApiError(err, "Failed to load price history"));
      } finally {
        if (!cancelled) {
          setLoadingHistory(false);
        }
      }
    }

    void loadHistory();
    return () => {
      cancelled = true;
    };
  }, [stockId, range, navigate]);

  function handleLogout(): void {
    localStorage.removeItem("access_token");
    navigate("/");
  }

  const changeTone: string = changeClassName(stock?.change ?? null);

  return (
    <div className="stock-details-page">
      <header className="stock-details-header">
        <span className="stock-details-logo">Stock Tracker</span>
        <div className="stock-details-header-actions">
          <button
            type="button"
            className="btn-outline"
            onClick={() => navigate("/dashboard")}
          >
            Back to dashboard
          </button>
          <button type="button" className="btn-outline" onClick={handleLogout}>
            Log out
          </button>
        </div>
      </header>

      <main className="stock-details-main">
        {loadingStock ? (
          <section className="dashboard-panel">
            <p className="stock-details-status">Loading stock information...</p>
          </section>
        ) : stockError ? (
          <section className="dashboard-panel">
            <p className="control-error">{stockError}</p>
            <button
              type="button"
              className="btn-solid btn-compact"
              onClick={() => navigate("/dashboard")}
            >
              Return to watchlist
            </button>
          </section>
        ) : stock ? (
          <>
            <section className="dashboard-panel stock-summary-panel">
              <h1 className="stock-summary-title">
                {stock.name}{" "}
                <span className="stock-summary-symbol">({stock.symbol})</span>
              </h1>
              <p className="stock-summary-price">{formatPrice(stock.close)}</p>
              <p className={`stock-summary-change ${changeTone}`}>
                {formatChange(stock.change)} ({formatPercentChange(stock.percent_change)}) Today
              </p>
            </section>

            <section className="dashboard-panel stock-chart-panel">
              <div className="stock-chart-header">
                <h2>Stock Price Chart</h2>
                <div className="stock-range-selectors" role="group" aria-label="Chart range">
                  {HISTORY_RANGES.map((option: HistoryRange) => (
                    <button
                      key={option}
                      type="button"
                      className={
                        range === option
                          ? "stock-range-btn stock-range-btn-active"
                          : "stock-range-btn"
                      }
                      onClick={() => setRange(option)}
                    >
                      {option}
                    </button>
                  ))}
                </div>
              </div>
              {loadingHistory ? (
                <p className="stock-details-status">Loading price history...</p>
              ) : historyError ? (
                <p className="control-error">{historyError}</p>
              ) : (
                <StockPriceChart bars={history} />
              )}
            </section>

            <section className="dashboard-panel stock-market-panel">
              <h2>Market Data</h2>
              <div className="market-data-grid">
                <div className="market-data-item">
                  <span className="market-data-label">Open</span>
                  <span className="market-data-value">{formatPrice(stock.open)}</span>
                </div>
                <div className="market-data-item">
                  <span className="market-data-label">Previous Close</span>
                  <span className="market-data-value">
                    {formatPrice(stock.previous_close)}
                  </span>
                </div>
                <div className="market-data-item">
                  <span className="market-data-label">Day High</span>
                  <span className="market-data-value">{formatPrice(stock.high)}</span>
                </div>
                <div className="market-data-item">
                  <span className="market-data-label">Day Low</span>
                  <span className="market-data-value">{formatPrice(stock.low)}</span>
                </div>
                <div className="market-data-item">
                  <span className="market-data-label">Volume</span>
                  <span className="market-data-value">{formatVolume(stock.volume)}</span>
                </div>
                <div className="market-data-item">
                  <span className="market-data-label">52W High</span>
                  <span className="market-data-value">
                    {formatPrice(stock.fifty_two_week_high)}
                  </span>
                </div>
                <div className="market-data-item">
                  <span className="market-data-label">52W Low</span>
                  <span className="market-data-value">
                    {formatPrice(stock.fifty_two_week_low)}
                  </span>
                </div>
              </div>
            </section>

            {stock.stock_summery ? (
              <section className="dashboard-panel stock-news-panel">
                <h2>News Summary</h2>
                <p className="stock-news-summary">{stock.stock_summery}</p>
              </section>
            ) : null}

            <StockNewsArticles stockId={stock.id} />
          </>
        ) : null}
      </main>
    </div>
  );
}
