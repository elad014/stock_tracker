import axios from "axios";

import type {
  HistoryRange,
  StockArticle,
  StockDetails,
  StockHistoryBar,
} from "../models/stocks";

const api = axios.create({ baseURL: "/stocks" });

api.interceptors.request.use((config) => {
  const token: string | null = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export async function fetchStockDetails(stockId: string): Promise<StockDetails> {
  const res = await api.get<StockDetails>(`/${stockId}`);
  return res.data;
}

export async function fetchStockHistory(
  stockId: string,
  range: HistoryRange = "1Y",
): Promise<StockHistoryBar[]> {
  const res = await api.get<StockHistoryBar[]>(`/${stockId}/history`, {
    params: { range },
  });
  return res.data;
}

export async function fetchStockArticles(
  stockId: string,
  limit: number = 100,
): Promise<StockArticle[]> {
  const res = await api.get<StockArticle[]>(`/${stockId}/articles`, {
    params: { limit },
  });
  return res.data;
}

export async function summarizeStockArticle(
  stockId: string,
  articleId: string,
): Promise<StockArticle> {
  const res = await api.post<StockArticle>(
    `/${stockId}/articles/${articleId}/summarize`,
  );
  return res.data;
}
