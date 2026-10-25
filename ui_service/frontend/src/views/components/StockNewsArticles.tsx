import axios from "axios";
import { useEffect, useRef, useState } from "react";

import type { StockArticle } from "../../models/stocks";
import { fetchStockArticles, summarizeStockArticle } from "../../services/stockService";

const POLL_INTERVAL_MS: number = 2000;
const MAX_POLL_ATTEMPTS: number = 45;
const CANNOT_EXTRACT_MESSAGE: string = "Cannot extract the article";
const NEWS_WINDOW_DAYS: number = 7;
const ALL_DAYS: string = "";
const DAY_ARTICLE_LIMIT: number = 200;

interface StockNewsArticlesProps {
  stockId: string;
}

interface NewsDayOption {
  value: string;
  label: string;
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

function formatIsoDate(day: Date): string {
  const year: number = day.getFullYear();
  const month: string = String(day.getMonth() + 1).padStart(2, "0");
  const date: string = String(day.getDate()).padStart(2, "0");
  return `${year}-${month}-${date}`;
}

function recentNewsDays(): NewsDayOption[] {
  const today: Date = new Date();
  const days: NewsDayOption[] = [];
  for (let offset: number = 0; offset < NEWS_WINDOW_DAYS; offset += 1) {
    const day: Date = new Date(today.getFullYear(), today.getMonth(), today.getDate() - offset);
    days.push({
      value: formatIsoDate(day),
      label: day.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      }),
    });
  }
  return days;
}

function isUnusableSummary(article: StockArticle): boolean {
  if (article.ai_summary_status === "failed") {
    return true;
  }
  const summary: string = (article.ai_summary || "").toLowerCase();
  return (
    summary.includes("enable javascript") ||
    summary.includes("javascript to continue") ||
    summary.includes("cannot extract the article")
  );
}

export default function StockNewsArticles({
  stockId,
}: StockNewsArticlesProps): JSX.Element | null {
  const [articles, setArticles] = useState<StockArticle[]>([]);
  const [selectedDay, setSelectedDay] = useState<string>(ALL_DAYS);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>("");
  const [busyIds, setBusyIds] = useState<string[]>([]);
  const cancelledRef = useRef<boolean>(false);
  const selectedDayRef = useRef<string>(ALL_DAYS);
  const dayOptions: NewsDayOption[] = recentNewsDays();
  selectedDayRef.current = selectedDay;

  useEffect(() => {
    let cancelled: boolean = false;
    cancelledRef.current = false;

    async function loadArticles(): Promise<void> {
      setLoading(true);
      setError("");
      setArticles([]);
      try {
        const data: StockArticle[] = await fetchStockArticles(
          stockId,
          selectedDay ? DAY_ARTICLE_LIMIT : 100,
          selectedDay || null,
        );
        if (!cancelled) {
          setArticles(data);
        }
      } catch {
        if (!cancelled) {
          setError("Failed to load news articles");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadArticles();
    return () => {
      cancelled = true;
      cancelledRef.current = true;
    };
  }, [stockId, selectedDay]);

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
      if (selectedDayRef.current !== selectedDay) {
        return;
      }
      const rows: StockArticle[] = await fetchStockArticles(
        stockId,
        selectedDay ? DAY_ARTICLE_LIMIT : 100,
        selectedDay || null,
      );
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

  return (
    <section className="dashboard-panel stock-articles-panel">
      <div className="stock-articles-header">
        <h2>Latest News</h2>
        <label className="news-day-field" htmlFor="news-day">
          Day
          <select
            id="news-day"
            value={selectedDay}
            onChange={(event) => setSelectedDay(event.target.value)}
          >
            <option value={ALL_DAYS}>Last 7 days</option>
            {dayOptions.map((option: NewsDayOption) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      {loading ? <p className="stock-details-status">Loading news articles...</p> : null}
      {error ? <p className="control-error">{error}</p> : null}
      {!loading && !error && articles.length === 0 ? (
        <p className="stock-details-status">
          {selectedDay
            ? "No news articles for this day."
            : "No news articles for the last 7 days."}
        </p>
      ) : null}
      {!loading && articles.length > 0 ? (
      <ul className="stock-articles-list">
        {articles.map((article: StockArticle) => {
          const busy: boolean = busyIds.includes(article.article_id);
          const pending: boolean = busy || article.ai_summary_status === "pending";
          const unusable: boolean = isUnusableSummary(article);
          const showReadySummary: boolean =
            article.ai_summary_status === "ready" &&
            Boolean(article.ai_summary) &&
            !unusable;
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

              {showReadySummary ? (
                <p className="stock-article-ai-summary">{article.ai_summary}</p>
              ) : null}

              {unusable ? (
                <p className="control-error">
                  {article.ai_summary_status === "failed"
                    ? article.ai_summary || CANNOT_EXTRACT_MESSAGE
                    : CANNOT_EXTRACT_MESSAGE}
                </p>
              ) : null}

              {showReadySummary || pending ? null : (
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
      ) : null}
    </section>
  );
}
