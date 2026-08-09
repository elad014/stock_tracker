export interface StockDetails {
  id: string;
  symbol: string;
  name: string;
  close: number | null;
  change: number | null;
  percent_change: number | null;
  previous_close: number | null;
  open: number | null;
  high: number | null;
  low: number | null;
  volume: number | null;
  fifty_two_week_high: number | null;
  fifty_two_week_low: number | null;
  stock_summery: string | null;
}

export interface StockHistoryBar {
  date: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number | null;
}

export type HistoryRange = "1D" | "5D" | "1M" | "3M" | "6M" | "1Y" | "5Y";

export type ArticleSummaryStatus = "none" | "pending" | "ready" | "failed";

export interface StockArticle {
  article_id: string;
  url: string;
  title: string;
  source: string | null;
  published_at: string | null;
  provider_summary: string | null;
  ai_summary: string | null;
  ai_summary_status: ArticleSummaryStatus;
  ai_summary_error: string | null;
}
