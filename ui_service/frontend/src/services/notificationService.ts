import axios from "axios";

import type { Notification } from "../models/notifications";

const api = axios.create({ baseURL: "/" });

api.interceptors.request.use((config) => {
  const token: string | null = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export async function fetchUnreadNotifications(): Promise<Notification[]> {
  const res = await api.get<Notification[]>("/notifications");
  return res.data;
}

export async function markNotificationRead(id: string): Promise<void> {
  await api.put(`/notifications/${id}/read`);
}
