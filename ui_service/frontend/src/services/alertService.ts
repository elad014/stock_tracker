import axios from "axios";

import type { AlertResponse, CreateAlertRequest } from "../models/alerts";

const api = axios.create({ baseURL: "/stocks" });

api.interceptors.request.use((config) => {
  const token: string | null = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export async function createAlert(
  stockId: string,
  req: CreateAlertRequest,
): Promise<AlertResponse> {
  const res = await api.post<AlertResponse>(`/${stockId}/alerts`, req);
  return res.data;
}
