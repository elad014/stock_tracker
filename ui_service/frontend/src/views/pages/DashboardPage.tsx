import { FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { fetchCurrentUser } from "../../services/authService";
import {
  addWatchlistStock,
  fetchWatchlist,
  removeWatchlistStock,
} from "../../services/watchlistService";
import type { WatchlistStock } from "../../models/watchlist";

type NewsItem = {
  id: string;
  headline: string;
  source: string;
  relatedSymbol: string;
};

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
};

const MOCK_NEWS: NewsItem[] = [
  {
    id: "1",
    headline: "Apple unveils new product roadmap amid strong services growth",
    source: "Market Wire",
    relatedSymbol: "AAPL",
  },
  {
    id: "2",
    headline: "Microsoft cloud revenue continues to outpace expectations",
    source: "Finance Daily",
    relatedSymbol: "MSFT",
  },
  {
    id: "3",
    headline: "Tesla delivery figures spark debate among analysts",
    source: "Auto Brief",
    relatedSymbol: "TSLA",
  },
  {
    id: "4",
    headline: "Tech stocks mixed as investors weigh rate outlook",
    source: "Market Wire",
    relatedSymbol: "AAPL",
  },
];

function formatNumber(value: number): string {
  return Number(value).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function formatPrice(price: number | null): string {
  if (price === null || price === undefined) {
    return "—";
  }
  return `$${formatNumber(price)}`;
}

function formatChange(change: number | null): string {
  if (change === null || change === undefined) {
    return "—";
  }
  const value: number = Number(change);
  const sign: string = value > 0 ? "+" : "";
  return `${sign}${formatNumber(value)}`;
}

function changeClassName(change: number | null): string {
  if (change === null || change === undefined || change === 0) {
    return "";
  }
  return change > 0 ? "change-up" : "change-down";
}

export default function DashboardPage(): JSX.Element {
  const navigate = useNavigate();
  const [stocks, setStocks] = useState<WatchlistStock[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [isAdmin, setIsAdmin] = useState<boolean>(false);
  const [newTicker, setNewTicker] = useState<string>("");
  const [removeStockId, setRemoveStockId] = useState<string>("");
  const [addError, setAddError] = useState<string>("");
  const [listError, setListError] = useState<string>("");
  const [chatOpen, setChatOpen] = useState<boolean>(false);
  const [chatInput, setChatInput] = useState<string>("");
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      text: "Ask me about your followed stocks. LLM connection coming soon.",
    },
  ]);

  async function loadWatchlist(): Promise<void> {
    setListError("");
    try {
      const data = await fetchWatchlist();
      setStocks(data);
    } catch (err: any) {
      if (err.response?.status === 401) {
        localStorage.removeItem("access_token");
        navigate("/login");
        return;
      }
      setListError(err.response?.data?.detail ?? "Failed to load watchlist");
    } finally {
      setLoading(false);
    }
  }

  async function loadUserRole(): Promise<void> {
    try {
      const user = await fetchCurrentUser();
      setIsAdmin(user.is_admin);
    } catch (err: any) {
      if (err.response?.status === 401) {
        localStorage.removeItem("access_token");
        navigate("/login");
      }
    }
  }

  useEffect(() => {
    void loadWatchlist();
    void loadUserRole();
  }, []);

  function handleLogout(): void {
    localStorage.removeItem("access_token");
    navigate("/");
  }

  async function handleAddStock(e: FormEvent): Promise<void> {
    e.preventDefault();
    setAddError("");
    const ticker: string = newTicker.trim().toUpperCase();
    if (!ticker) {
      setAddError("Enter a ticker symbol");
      return;
    }
    if (!/^[A-Z]{1,5}(?:[.-][A-Z])?$/.test(ticker)) {
      setAddError("Invalid ticker (e.g. AAPL, BRK.A)");
      return;
    }

    try {
      await addWatchlistStock(ticker);
      setNewTicker("");
      await loadWatchlist();
    } catch (err: any) {
      setAddError(err.response?.data?.detail ?? "Failed to add stock");
    }
  }

  async function handleRemoveStock(e: FormEvent): Promise<void> {
    e.preventDefault();
    if (!removeStockId) {
      return;
    }
    try {
      await removeWatchlistStock(removeStockId);
      setRemoveStockId("");
      await loadWatchlist();
    } catch (err: any) {
      setAddError(err.response?.data?.detail ?? "Failed to remove stock");
    }
  }

  function handleSendChat(e: FormEvent): void {
    e.preventDefault();
    const text: string = chatInput.trim();
    if (!text) {
      return;
    }
    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: "user",
      text,
    };
    const reply: ChatMessage = {
      id: `a-${Date.now()}`,
      role: "assistant",
      text: "LLM connection coming soon. Your message was received.",
    };
    setMessages((prev: ChatMessage[]) => [...prev, userMsg, reply]);
    setChatInput("");
  }

  const visibleNews: NewsItem[] = MOCK_NEWS.filter(
    (item: NewsItem) =>
      stocks.length === 0 ||
      stocks.some((s: WatchlistStock) => s.symbol === item.relatedSymbol),
  );

  return (
    <div className="dashboard-page">
      <header className="dashboard-header">
        <span className="dashboard-logo">Stock Tracker</span>
        <div className="dashboard-header-actions">
          {isAdmin ? (
            <button
              type="button"
              className="btn-outline"
              onClick={() => navigate("/admin")}
            >
              Admin
            </button>
          ) : null}
          <button
            type="button"
            className="btn-outline"
            onClick={() => navigate("/settings")}
          >
            Settings
          </button>
          <button type="button" className="btn-outline" onClick={handleLogout}>
            Log out
          </button>
        </div>
      </header>

      <main className="dashboard-main">
        <section className="dashboard-panel">
          <h1>Your followed stocks</h1>

          <div className="stock-controls">
            <form className="stock-control-form" onSubmit={handleAddStock}>
              <label htmlFor="new-ticker">Add stock</label>
              <div className="stock-control-row">
                <input
                  id="new-ticker"
                  type="text"
                  value={newTicker}
                  onChange={(e) => setNewTicker(e.target.value)}
                  placeholder="e.g. AAPL or BRK-A"
                  maxLength={7}
                />
                <button type="submit" className="btn-solid btn-compact">
                  Add
                </button>
              </div>
              {addError && <p className="control-error">{addError}</p>}
            </form>

            <form className="stock-control-form" onSubmit={handleRemoveStock}>
              <label htmlFor="remove-ticker">Remove stock</label>
              <div className="stock-control-row">
                <select
                  id="remove-ticker"
                  value={removeStockId}
                  onChange={(e) => setRemoveStockId(e.target.value)}
                >
                  <option value="">Select a stock</option>
                  {stocks.map((stock: WatchlistStock) => (
                    <option key={stock.id} value={stock.id}>
                      {stock.symbol}
                    </option>
                  ))}
                </select>
                <button
                  type="submit"
                  className="btn-outline btn-compact"
                  disabled={!removeStockId}
                >
                  Remove
                </button>
              </div>
            </form>
          </div>

          {listError && <p className="control-error">{listError}</p>}

          <div className="table-wrap">
            <table className="stocks-table">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Price</th>
                  <th>Change</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td colSpan={3} className="empty-cell">
                      Loading watchlist...
                    </td>
                  </tr>
                ) : stocks.length === 0 ? (
                  <tr>
                    <td colSpan={3} className="empty-cell">
                      No stocks followed yet. Add a ticker above.
                    </td>
                  </tr>
                ) : (
                  stocks.map((stock: WatchlistStock) => (
                    <tr key={stock.id}>
                      <td className="symbol-cell">{stock.symbol}</td>
                      <td>{formatPrice(stock.price)}</td>
                      <td className={changeClassName(stock.change)}>
                        {formatChange(stock.change)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section className="dashboard-panel news-panel">
          <h2>News</h2>
          {visibleNews.length === 0 ? (
            <p className="news-empty">No news for your followed stocks yet.</p>
          ) : (
            <ul className="news-list">
              {visibleNews.map((item: NewsItem) => (
                <li key={item.id} className="news-item">
                  <span className="news-symbol">{item.relatedSymbol}</span>
                  <p className="news-headline">{item.headline}</p>
                  <span className="news-source">{item.source}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </main>

      <button
        type="button"
        className="chat-fab"
        onClick={() => setChatOpen(true)}
        aria-label="Open chat"
      >
        Chat
      </button>

      {chatOpen && (
        <div className="chat-overlay" role="dialog" aria-label="Assistant chat">
          <div className="chat-panel">
            <div className="chat-header">
              <h2>Assistant</h2>
              <button
                type="button"
                className="btn-outline btn-compact"
                onClick={() => setChatOpen(false)}
              >
                Close
              </button>
            </div>
            <div className="chat-messages">
              {messages.map((msg: ChatMessage) => (
                <div
                  key={msg.id}
                  className={
                    msg.role === "user" ? "chat-bubble chat-bubble-user" : "chat-bubble"
                  }
                >
                  {msg.text}
                </div>
              ))}
            </div>
            <form className="chat-input-row" onSubmit={handleSendChat}>
              <input
                type="text"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                placeholder="Ask about your portfolio..."
              />
              <button type="submit" className="btn-solid btn-compact">
                Send
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
