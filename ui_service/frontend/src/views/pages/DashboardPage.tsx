import { ChangeEvent, FormEvent, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { fetchCurrentUser } from "../../services/authService";
import {
  addWatchlistStock,
  fetchWatchlist,
  removeWatchlistStock,
} from "../../services/watchlistService";
import {
  createDocumentFolder,
  deleteDocumentFile,
  deleteDocumentFolder,
  fetchDocumentTree,
  fetchDownloadUrl,
  moveDocument,
  uploadDocument,
} from "../../services/documentService";
import DocumentTree from "../components/DocumentTree";
import type { DocumentTree as DocumentTreeData, TreeNode } from "../../models/documents";
import type { WatchlistStock } from "../../models/watchlist";
import {
  changeClassName,
  formatChange,
  formatPrice,
} from "../../utils/formatters";

type NewsItem = {
  id: string;
  headline: string;
  relatedSymbol: string;
};

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
};

function collectFolders(nodes: TreeNode[]): string[] {
  const paths: string[] = [];
  for (const node of nodes) {
    if (node.type === "folder") {
      paths.push(node.path);
      paths.push(...collectFolders(node.children));
    }
  }
  return paths;
}

function parentFolder(path: string): string {
  const slash: number = path.lastIndexOf("/");
  return slash === -1 ? "" : path.slice(0, slash);
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
  const [docTree, setDocTree] = useState<DocumentTreeData | null>(null);
  const [docError, setDocError] = useState<string>("");
  const [docBusy, setDocBusy] = useState<boolean>(false);
  const [selectedFolder, setSelectedFolder] = useState<string>("");
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [newFolderName, setNewFolderName] = useState<string>("");
  const fileInputRef = useRef<HTMLInputElement | null>(null);

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

  async function loadDocuments(): Promise<void> {
    setDocError("");
    try {
      const tree = await fetchDocumentTree();
      setDocTree(tree);
    } catch (err: any) {
      if (err.response?.status === 401) {
        localStorage.removeItem("access_token");
        navigate("/login");
        return;
      }
      setDocError(err.response?.data?.detail ?? "Failed to load documents");
    }
  }

  useEffect(() => {
    void loadWatchlist();
    void loadUserRole();
    void loadDocuments();
  }, []);

  function handleToggleFolder(path: string): void {
    setExpanded((prev: Record<string, boolean>) => ({
      ...prev,
      [path]: !prev[path],
    }));
  }

  function handleSelectFolder(path: string): void {
    setSelectedFolder((prev: string) => (prev === path ? "" : path));
    setExpanded((prev: Record<string, boolean>) => ({ ...prev, [path]: true }));
  }

  async function handleUploadFile(e: ChangeEvent<HTMLInputElement>): Promise<void> {
    const file: File | undefined = e.target.files?.[0];
    if (!file) {
      return;
    }
    setDocError("");
    setDocBusy(true);
    try {
      await uploadDocument(file, selectedFolder);
      await loadDocuments();
    } catch (err: any) {
      setDocError(err.response?.data?.detail ?? "Upload failed");
    } finally {
      setDocBusy(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  }

  async function handleCreateFolder(e: FormEvent): Promise<void> {
    e.preventDefault();
    const name: string = newFolderName.trim();
    if (!name) {
      return;
    }
    setDocError("");
    setDocBusy(true);
    try {
      const path: string = selectedFolder ? `${selectedFolder}/${name}` : name;
      await createDocumentFolder(path);
      setNewFolderName("");
      setSelectedFolder(path);
      setExpanded((prev: Record<string, boolean>) => ({ ...prev, [path]: true }));
      await loadDocuments();
    } catch (err: any) {
      setDocError(err.response?.data?.detail ?? "Could not create folder");
    } finally {
      setDocBusy(false);
    }
  }

  async function handleDeleteNode(node: TreeNode): Promise<void> {
    const label: string = node.type === "folder" ? "folder" : "file";
    if (!window.confirm(`Delete ${label} "${node.name}"?`)) {
      return;
    }
    setDocError("");
    setDocBusy(true);
    try {
      if (node.type === "folder") {
        await deleteDocumentFolder(node.path);
        if (selectedFolder === node.path) {
          setSelectedFolder("");
        }
      } else {
        await deleteDocumentFile(node.path);
      }
      await loadDocuments();
    } catch (err: any) {
      setDocError(err.response?.data?.detail ?? `Could not delete ${label}`);
    } finally {
      setDocBusy(false);
    }
  }

  async function handleMoveFile(node: TreeNode): Promise<void> {
    if (parentFolder(node.path) === selectedFolder) {
      setDocError("Choose a different folder in Put files in, then click Move.");
      return;
    }
    setDocError("");
    setDocBusy(true);
    try {
      await moveDocument(node.path, selectedFolder);
      await loadDocuments();
    } catch (err: any) {
      setDocError(err.response?.data?.detail ?? "Could not move file");
    } finally {
      setDocBusy(false);
    }
  }

  async function handleOpenFile(node: TreeNode): Promise<void> {
    setDocError("");
    try {
      const url: string = await fetchDownloadUrl(node.path);
      window.open(url, "_blank", "noopener,noreferrer");
    } catch (err: any) {
      setDocError(err.response?.data?.detail ?? "Could not open file");
    }
  }

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

  const visibleNews: NewsItem[] = stocks
    .filter(
      (stock: WatchlistStock) =>
        typeof stock.stock_summery === "string" && stock.stock_summery.trim() !== "",
    )
    .map((stock: WatchlistStock) => ({
      id: stock.id,
      relatedSymbol: stock.symbol,
      headline: stock.stock_summery as string,
    }));
  const folderPaths: string[] = docTree ? collectFolders(docTree.nodes) : [];
  const uploadLabel: string = selectedFolder
    ? `Upload PDF to ${selectedFolder}`
    : "Upload PDF";

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
        <section className="dashboard-panel documents-panel">
          <div className="documents-header">
            <h2>My documents</h2>
            {docTree && (
              <span className="documents-count">
                {docTree.file_count} / {docTree.max_files} files
              </span>
            )}
          </div>

          <p className="documents-target">
            <label htmlFor="document-folder">Put files in</label>
            <select
              id="document-folder"
              value={selectedFolder}
              onChange={(e) => setSelectedFolder(e.target.value)}
              disabled={docBusy}
            >
              <option value="">My documents</option>
              {folderPaths.map((path: string) => (
                <option key={path} value={path}>
                  {path}
                </option>
              ))}
            </select>
          </p>

          <div className="documents-actions">
            <input
              ref={fileInputRef}
              id="document-upload"
              type="file"
              accept="application/pdf,.pdf"
              className="doc-file-input"
              onChange={handleUploadFile}
              disabled={
                docBusy || (docTree ? docTree.file_count >= docTree.max_files : false)
              }
            />
            <label htmlFor="document-upload" className="btn-solid btn-compact doc-upload-btn">
              {docBusy ? "Working..." : uploadLabel}
            </label>

            <form className="doc-folder-form" onSubmit={handleCreateFolder}>
              <input
                type="text"
                value={newFolderName}
                onChange={(e) => setNewFolderName(e.target.value)}
                placeholder="New folder name"
                maxLength={64}
                disabled={docBusy}
              />
              <button
                type="submit"
                className="btn-outline btn-compact"
                disabled={docBusy || !newFolderName.trim()}
              >
                Add
              </button>
            </form>
          </div>

          {docTree && docTree.file_count >= docTree.max_files && (
            <p className="documents-note">
              File limit reached. Delete a file to upload another.
            </p>
          )}
          {docError && <p className="control-error">{docError}</p>}

          {docTree === null ? (
            <p className="documents-note">Loading documents...</p>
          ) : docTree.nodes.length === 0 ? (
            <p className="documents-note">
              No documents yet. Upload a PDF to get started.
            </p>
          ) : (
            <DocumentTree
              nodes={docTree.nodes}
              selectedFolder={selectedFolder}
              expanded={expanded}
              busy={docBusy}
              onToggleFolder={handleToggleFolder}
              onSelectFolder={handleSelectFolder}
              onOpenFile={handleOpenFile}
              onMoveFile={handleMoveFile}
              onDelete={handleDeleteNode}
            />
          )}
        </section>

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
                  placeholder="e.g. AAPL or BRK.A"
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
                    <tr
                      key={stock.id}
                      className="stocks-table-row-clickable"
                      onClick={() => navigate(`/stock/${stock.id}`)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          navigate(`/stock/${stock.id}`);
                        }
                      }}
                      tabIndex={0}
                      role="link"
                      aria-label={`Open details for ${stock.symbol}`}
                    >
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
