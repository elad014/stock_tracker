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
  is_admin: boolean;
}

export interface CurrentUser {
  id: string;
  user_name: string;
  email: string;
  phone_number: string;
  is_admin: boolean;
}

export interface UpdateSettingsPayload {
  user_name?: string;
  email?: string;
  phone_number?: string;
  old_password?: string;
  new_password?: string;
}

export interface UpdateSettingsResponse {
  id: string;
  user_name: string;
  email: string;
  phone_number: string;
  message: string;
  access_token?: string | null;
}

export interface MessageResponse {
  message: string;
}
