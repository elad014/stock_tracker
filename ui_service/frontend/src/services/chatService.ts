import axios from "axios";

export interface ChatReply {
  content: string;
  model: string;
}

const api = axios.create({
  baseURL: "/chat",
  timeout: 180000,
});

api.interceptors.request.use((config) => {
  const token: string | null = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export async function sendChatMessage(
  message: string,
  documentId?: string,
): Promise<ChatReply> {
  const body: { message: string; document_id?: string } = { message };
  if (documentId) {
    body.document_id = documentId;
  }
  const res = await api.post<ChatReply>("", body);
  return res.data;
}

export function chatErrorMessage(err: unknown): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } }).response
    ?.data?.detail;
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }
  return "Chat request failed";
}
