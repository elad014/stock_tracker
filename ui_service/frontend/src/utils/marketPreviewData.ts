import type { StockHistoryBar } from "../models/stocks";

export type MarketQuote = {
  symbol: string;
  name: string;
  price: number;
  change: number;
  percentChange: number;
  series: number[];
};

type MarketSeed = {
  symbol: string;
  name: string;
  start: number;
  drift: number;
  seed: number;
};

const SERIES_LENGTH: number = 32;

const MARKET_SEEDS: MarketSeed[] = [
  { symbol: "AAPL", name: "Apple", start: 221.4, drift: 0.0018, seed: 17 },
  { symbol: "MSFT", name: "Microsoft", start: 412.8, drift: 0.0011, seed: 23 },
  { symbol: "NVDA", name: "NVIDIA", start: 118.6, drift: 0.0024, seed: 31 },
  { symbol: "GOOGL", name: "Alphabet", start: 174.2, drift: 0.0009, seed: 41 },
  { symbol: "AMZN", name: "Amazon", start: 186.5, drift: 0.0014, seed: 53 },
  { symbol: "TSLA", name: "Tesla", start: 248.1, drift: -0.0006, seed: 67 },
  { symbol: "META", name: "Meta", start: 511.3, drift: 0.0016, seed: 79 },
  { symbol: "SPY", name: "S&P 500 ETF", start: 546.7, drift: 0.0008, seed: 97 },
  { symbol: "QQQ", name: "Nasdaq 100 ETF", start: 478.9, drift: 0.0012, seed: 113 },
  { symbol: "BTC", name: "Bitcoin", start: 64280, drift: 0.0015, seed: 131 },
];

export const FEATURED_SYMBOLS: string[] = ["SPY", "QQQ", "AAPL", "NVDA"];

function nextRandom(state: number): number {
  return (state * 16807) % 2147483647;
}

function buildSeries(start: number, drift: number, seed: number): number[] {
  const values: number[] = [Number(start.toFixed(2))];
  let state: number = seed;
  for (let index = 1; index < SERIES_LENGTH; index += 1) {
    state = nextRandom(state);
    const noise: number = (state - 1) / 2147483646 - 0.5;
    const previous: number = values[index - 1];
    const next: number = previous * (1 + drift + noise * 0.018);
    values.push(Number(next.toFixed(2)));
  }
  return values;
}

function quoteFromSeed(seed: MarketSeed): MarketQuote {
  const series: number[] = buildSeries(seed.start, seed.drift, seed.seed);
  const price: number = series[series.length - 1];
  const open: number = series[0];
  const change: number = Number((price - open).toFixed(2));
  const percentChange: number =
    open === 0 ? 0 : Number(((change / open) * 100).toFixed(2));
  return {
    symbol: seed.symbol,
    name: seed.name,
    price,
    change,
    percentChange,
    series,
  };
}

export function createMarketQuotes(): MarketQuote[] {
  return MARKET_SEEDS.map((seed: MarketSeed) => quoteFromSeed(seed));
}

export function jitterMarketQuotes(quotes: MarketQuote[]): MarketQuote[] {
  return quotes.map((quote: MarketQuote) => {
    const magnitude: number = Math.max(0.02, quote.price * 0.00035);
    const noise: number = (Math.random() - 0.5) * 2 * magnitude;
    const nextPrice: number = Number((quote.price + noise).toFixed(2));
    const series: number[] = [...quote.series.slice(0, -1), nextPrice];
    return {
      ...quote,
      price: nextPrice,
      series,
    };
  });
}

export function seriesToHistoryBars(series: number[]): StockHistoryBar[] {
  const end: Date = new Date(2026, 7, 20);
  return series.map((close: number, index: number) => {
    const date: Date = new Date(end);
    date.setDate(end.getDate() - (series.length - 1 - index));
    const year: string = String(date.getFullYear());
    const month: string = String(date.getMonth() + 1).padStart(2, "0");
    const day: string = String(date.getDate()).padStart(2, "0");
    return {
      date: `${year}-${month}-${day}`,
      open: null,
      high: null,
      low: null,
      close,
      volume: null,
    };
  });
}
