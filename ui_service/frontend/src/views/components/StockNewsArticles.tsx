import axios from "axios";
import { useEffect, useRef, useState } from "react";

import type { StockArticle } from "../../models/stocks";
import { fetchStockArticles, summarizeStockArticle } from "../../services/stockService";

const POLL_INTERVAL_MS: number = 2000;
const MAX_POLL_ATTEMPTS: number = 45;

interface StockNewsArticlesProps {
  stockId: string;
}

function formatPublishedAt(value: string | null): string {
  if (!value) {
    return "";
  }
  const parsed: Date = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "";
  }
  return parsed.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export default function StockNewsArticles({
  stockId,
}: StockNewsArticlesProps): JSX.Element | null {
  const [articles, setArticles] = useState<StockArticle[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>("");
  const [busyIds, setBusyIds] = useState<string[]>([]);
  const cancelledRef = useRef<boolean>(false);

  useEffect(() => {
    cancelledRef.current = false;

    async function loadArticles(): Promise<void> {
      setLoading(true);
      setError("");
      try {
        const data: StockArticle[] = await fetchStockArticles(stockId);
        if (!cancelledRef.current) {
          setArticles(data);
        }
      } catch {
        if (!cancelledRef.current) {
          setError("Failed to load news articles");
        }
      } finally {
        if (!cancelledRef.current) {
          setLoading(false);
        }
      }
    }

    void loadArticles();
    return () => {
      cancelledRef.current = true;
    };
  }, [stockId]);

  function replaceArticle(updated: StockArticle): void {
    setArticles((current: StockArticle[]) =>
      current.map((item: StockArticle) =>
        item.article_id === updated.article_id
          ? { ...item, ...updated, source: item.source, published_at: item.published_at }
          : item,
      ),
    );
  }

  async function pollUntilReady(articleId: string): Promise<void> {
    for (let attempt: number = 0; attempt < MAX_POLL_ATTEMPTS; attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
      if (cancelledRef.current) {
        return;
      }
      const rows: StockArticle[] = await fetchStockArticles(stockId);
      const match: StockArticle | undefined = rows.find(
        (item: StockArticle) => item.article_id === articleId,
      );
      if (!match) {
        return;
      }
      if (match.ai_summary_status !== "pending") {
        replaceArticle(match);
        return;
      }
    }
  }

  async function handleSummarize(articleId: string): Promise<void> {
    setBusyIds((current: string[]) => [...current, articleId]);
    try {
      const result: StockArticle = await summarizeStockArticle(stockId, articleId);
      replaceArticle(result);
      if (result.ai_summary_status === "pending") {
        await pollUntilReady(articleId);
      }
    } catch (err: unknown) {
      if (!cancelledRef.current) {
        if (axios.isAxiosError(err) && err.response?.status === 429) {
          setError("Too many summaries right now. Please try again in a minute.");
        } else {
          setError("Failed to summarize the article");
        }
      }
    } finally {
      if (!cancelledRef.current) {
        setBusyIds((current: string[]) =>
          current.filter((id: string) => id !== articleId),
        );
      }
    }
  }

  if (loading) {
    return (
      <section className="dashboard-panel stock-articles-panel">
        <h2>Latest News</h2>
        <p className="stock-details-status">Loading news articles...</p>
      </section>
    );
  }

  if (!articles.length && !error) {
    return null;
  }

  return (
    <section className="dashboard-panel stock-articles-panel">
      <h2>Latest News</h2>
      {error ? <p className="control-error">{error}</p> : null}
      <ul className="stock-articles-list">
        {articles.map((article: StockArticle) => {
          const busy: boolean = busyIds.includes(article.article_id);
          const pending: boolean = busy || article.ai_summary_status === "pending";
          const published: string = formatPublishedAt(article.published_at);
          return (
            <li key={article.article_id} className="stock-article-item">
              <a
                className="stock-article-title"
                href={article.url}
                target="_blank"
                rel="noopener noreferrer"
              >
                {article.title}
              </a>
              <p className="stock-article-meta">
                {[article.source, published].filter(Boolean).join(" • ")}
              </p>
              {article.provider_summary ? (
                <p className="stock-article-blurb">{article.provider_summary}</p>
              ) : null}

              {article.ai_summary ? (
                <p className="stock-article-ai-summary">{article.ai_summary}</p>
              ) : null}

              {article.ai_summary_status === "failed" && !article.ai_summary ? (
                <p className="control-error">
                  Could not summarize this article. Try again.
                </p>
              ) : null}

              {article.ai_summary ? null : (
                <button
                  type="button"
                  className="btn-solid btn-compact"
                  onClick={() => void handleSummarize(article.article_id)}
                  disabled={pending}
                >
                  {pending ? "Summarizing..." : "Summarize article"}
                </button>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
