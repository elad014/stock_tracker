import axios from "axios";

export interface WatchlistStock {
  id: string;
  name: string;
  price: number | null;
  trend: string | number | null;
}

const api = axios.create({ baseURL: "/watchlist" });

api.interceptors.request.use((config) => {
  const token: string | null = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export async function fetchWatchlist(): Promise<WatchlistStock[]> {
  const res = await api.get<WatchlistStock[]>("");
  return res.data;
}

export async function addWatchlistStock(name: string): Promise<WatchlistStock> {
  const res = await api.post<WatchlistStock>("", { name });
  return res.data;
}

export async function removeWatchlistStock(stockId: string): Promise<string> {
  const res = await api.delete<{ message: string }>(`/${stockId}`);
  return res.data.message;
}
