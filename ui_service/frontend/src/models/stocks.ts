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
