import { useEffect, useState } from "react";

import {
  createMarketQuotes,
  jitterMarketQuotes,
  type MarketQuote,
} from "./marketPreviewData";

export function useMarketQuotes(): MarketQuote[] {
  const [quotes, setQuotes] = useState<MarketQuote[]>(() => createMarketQuotes());

  useEffect(() => {
    const timer: number = window.setInterval(() => {
      setQuotes((current: MarketQuote[]) => jitterMarketQuotes(current));
    }, 2500);
    return () => {
      window.clearInterval(timer);
    };
  }, []);

  return quotes;
}
