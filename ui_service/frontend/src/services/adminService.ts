import axios from "axios";

import type {
  AdminStock,
  AdminUser,
  RegisterUserPayload,
  UpdateUserPayload,
} from "../models/admin";

const api = axios.create({ baseURL: "/admin" });

api.interceptors.request.use((config) => {
  const token: string | null = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export async function fetchAdminUsers(): Promise<AdminUser[]> {
  const res = await api.get<AdminUser[]>("/users");
  return res.data;
}

export async function createAdminUser(data: RegisterUserPayload): Promise<AdminUser> {
  const res = await api.post<AdminUser>("/users", data);
  return res.data;
}

export async function updateAdminUser(
  userId: string,
  data: UpdateUserPayload,
): Promise<AdminUser> {
  const res = await api.put<AdminUser>(`/users/${userId}`, data);
  return res.data;
}

export async function setAdminUserPassword(
  userId: string,
  newPassword: string,
): Promise<string> {
  const res = await api.put<{ message: string }>(`/users/${userId}/password`, {
    new_password: newPassword,
  });
  return res.data.message;
}

export async function removeUserAdminRole(userId: string): Promise<string> {
  const res = await api.delete<{ message: string }>(`/users/${userId}/admin`);
  return res.data.message;
}

export async function removeUserLock(userId: string): Promise<string> {
  const res = await api.delete<{ message: string }>(`/users/${userId}/lock`);
  return res.data.message;
}

export async function deleteAdminUser(userId: string): Promise<string> {
  const res = await api.delete<{ message: string }>(`/users/${userId}`);
  return res.data.message;
}

export async function fetchAdminStocks(): Promise<AdminStock[]> {
  const res = await api.get<AdminStock[]>("/stocks");
  return res.data;
}

export async function createAdminStock(
  name: string,
  userIds: string[],
): Promise<AdminStock> {
  const res = await api.post<AdminStock>("/stocks", {
    name,
    user_ids: userIds,
  });
  return res.data;
}

export async function deleteAdminStock(stockId: string): Promise<string> {
  const res = await api.delete<{ message: string }>(`/stocks/${stockId}`);
  return res.data.message;
}

export async function assignStockToUser(
  userId: string,
  stockId: string,
): Promise<AdminStock> {
  const res = await api.post<AdminStock>(`/users/${userId}/watchlist`, {
    stock_id: stockId,
  });
  return res.data;
}

export async function removeStockFromUser(
  userId: string,
  stockId: string,
): Promise<string> {
  const res = await api.delete<{ message: string }>(
    `/users/${userId}/watchlist/${stockId}`,
  );
  return res.data.message;
}
