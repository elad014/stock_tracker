export interface WatchlistStock {
  id: string;
  symbol: string;
  price: number | null;
  change: number | null;
  stock_summery: string | null;
}
