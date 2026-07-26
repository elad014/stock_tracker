import axios from "axios";

export interface AdminStock {
  id: string;
  name: string;
  price: number | null;
  trend: string | number | null;
}

export interface AdminUser {
  id: string;
  user_name: string;
  email: string;
  phone_number: string;
  followed_stocks: AdminStock[];
}

export interface RegisterUserPayload {
  user_name: string;
  email: string;
  password: string;
  phone_number: string;
}

const api = axios.create({ baseURL: "/admin" });

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
  data: RegisterUserPayload,
): Promise<AdminUser> {
  const res = await api.put<AdminUser>(`/users/${userId}`, data);
  return res.data;
}

export async function deleteAdminUser(userId: string): Promise<string> {
  const res = await api.delete<{ message: string }>(`/users/${userId}`);
  return res.data.message;
}

export async function fetchAdminStocks(): Promise<AdminStock[]> {
  const res = await api.get<AdminStock[]>("/stocks");
  return res.data;
}

export async function createAdminStock(name: string): Promise<AdminStock> {
  const res = await api.post<AdminStock>("/stocks", { name });
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
