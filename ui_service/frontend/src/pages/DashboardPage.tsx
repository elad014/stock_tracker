import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";

type Stock = {
  symbol: string;
  name: string;
  price: number;
  changePct: number;
};

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

const INITIAL_STOCKS: Stock[] = [
  { symbol: "AAPL", name: "Apple Inc.", price: 214.32, changePct: 1.24 },
  { symbol: "MSFT", name: "Microsoft Corp.", price: 428.15, changePct: -0.42 },
  { symbol: "TSLA", name: "Tesla Inc.", price: 248.9, changePct: 2.18 },
];

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

const KNOWN_NAMES: Record<string, string> = {
  AAPL: "Apple Inc.",
  MSFT: "Microsoft Corp.",
  TSLA: "Tesla Inc.",
  GOOGL: "Alphabet Inc.",
  AMZN: "Amazon.com Inc.",
  NVDA: "NVIDIA Corp.",
  META: "Meta Platforms Inc.",
};

function createMockStock(symbol: string): Stock {
  const upper: string = symbol.toUpperCase();
  const price: number = Math.round((50 + Math.random() * 450) * 100) / 100;
  const changePct: number = Math.round((Math.random() * 6 - 3) * 100) / 100;
  return {
    symbol: upper,
    name: KNOWN_NAMES[upper] ?? `${upper} Holdings`,
    price,
    changePct,
  };
}

export default function DashboardPage(): JSX.Element {
  const navigate = useNavigate();
  const [stocks, setStocks] = useState<Stock[]>(INITIAL_STOCKS);
  const [newTicker, setNewTicker] = useState<string>("");
  const [removeSymbol, setRemoveSymbol] = useState<string>("");
  const [addError, setAddError] = useState<string>("");
  const [chatOpen, setChatOpen] = useState<boolean>(false);
  const [chatInput, setChatInput] = useState<string>("");
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      text: "Ask me about your followed stocks. LLM connection coming soon.",
    },
  ]);

  function handleLogout(): void {
    localStorage.removeItem("access_token");
    navigate("/");
  }

  function handleAddStock(e: FormEvent): void {
    e.preventDefault();
    setAddError("");
    const ticker: string = newTicker.trim().toUpperCase();
    if (!ticker) {
      setAddError("Enter a ticker symbol");
      return;
    }
    if (!/^[A-Z]{1,5}$/.test(ticker)) {
      setAddError("Use 1–5 letters only");
      return;
    }
    if (stocks.some((s: Stock) => s.symbol === ticker)) {
      setAddError("You already follow this stock");
      return;
    }
    setStocks((prev: Stock[]) => [...prev, createMockStock(ticker)]);
    setNewTicker("");
    if (!removeSymbol) {
      setRemoveSymbol(ticker);
    }
  }

  function handleRemoveStock(e: FormEvent): void {
    e.preventDefault();
    if (!removeSymbol) {
      return;
    }
    setStocks((prev: Stock[]) => prev.filter((s: Stock) => s.symbol !== removeSymbol));
    setRemoveSymbol("");
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
      stocks.length === 0 || stocks.some((s: Stock) => s.symbol === item.relatedSymbol),
  );

  return (
    <div className="dashboard-page">
      <header className="dashboard-header">
        <span className="dashboard-logo">Stock Tracker</span>
        <button type="button" className="btn-outline" onClick={handleLogout}>
          Log out
        </button>
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
                  placeholder="e.g. NVDA"
                  maxLength={5}
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
                  value={removeSymbol}
                  onChange={(e) => setRemoveSymbol(e.target.value)}
                >
                  <option value="">Select a stock</option>
                  {stocks.map((stock: Stock) => (
                    <option key={stock.symbol} value={stock.symbol}>
                      {stock.symbol}
                    </option>
                  ))}
                </select>
                <button
                  type="submit"
                  className="btn-outline btn-compact"
                  disabled={!removeSymbol}
                >
                  Remove
                </button>
              </div>
            </form>
          </div>

          <div className="table-wrap">
            <table className="stocks-table">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Name</th>
                  <th>Price</th>
                  <th>Change %</th>
                </tr>
              </thead>
              <tbody>
                {stocks.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="empty-cell">
                      No stocks followed yet. Add a ticker above.
                    </td>
                  </tr>
                ) : (
                  stocks.map((stock: Stock) => (
                    <tr key={stock.symbol}>
                      <td className="symbol-cell">{stock.symbol}</td>
                      <td>{stock.name}</td>
                      <td>${stock.price.toFixed(2)}</td>
                      <td className={stock.changePct >= 0 ? "change-up" : "change-down"}>
                        {stock.changePct >= 0 ? "+" : ""}
                        {stock.changePct.toFixed(2)}%
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
