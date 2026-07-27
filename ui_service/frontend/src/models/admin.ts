import type { WatchlistStock } from "./watchlist";

export interface AdminStock extends WatchlistStock {}

export interface AdminUser {
  id: string;
  user_name: string;
  email: string;
  phone_number: string;
  admin?: string | null;
  lock?: string | null;
  followed_stocks: AdminStock[];
}

export interface RegisterUserPayload {
  user_name: string;
  email: string;
  password: string;
  phone_number: string;
  admin?: string;
  lock?: string;
}

export interface UpdateUserPayload {
  user_name: string;
  email: string;
  phone_number: string;
  admin?: string | null;
  lock?: string | null;
}
