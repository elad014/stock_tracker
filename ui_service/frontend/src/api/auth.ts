import axios from "axios";

const api = axios.create({ baseURL: "/auth" });

export interface RegisterPayload {
  user_name: string;
  email: string;
  password: string;
  phone_number: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface RegisterResponse {
  id: string;
  user_name: string;
  email: string;
  phone_number: string;
}

export async function registerUser(data: RegisterPayload): Promise<RegisterResponse> {
  const res = await api.post<RegisterResponse>("/register", data);
  return res.data;
}

export async function loginUser(data: LoginPayload): Promise<TokenResponse> {
  const res = await api.post<TokenResponse>("/login", data);
  return res.data;
}

export async function requestPasswordReset(email: string): Promise<string> {
  const res = await api.post<{ message: string }>("/password-reset-request", { email });
  return res.data.message;
}

export async function confirmPasswordReset(token: string, new_password: string): Promise<string> {
  const res = await api.post<{ message: string }>("/password-reset-confirm", { token, new_password });
  return res.data.message;
}
