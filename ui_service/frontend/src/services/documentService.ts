import axios from "axios";

import type { DocumentTree, TreeNode } from "../models/documents";

const api = axios.create({ baseURL: "/documents" });

api.interceptors.request.use((config) => {
  const token: string | null = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export async function fetchDocumentTree(): Promise<DocumentTree> {
  const res = await api.get<DocumentTree>("/tree");
  return res.data;
}

export async function uploadDocument(file: File, folder: string): Promise<TreeNode> {
  const form = new FormData();
  form.append("file", file);
  form.append("folder", folder);
  const res = await api.post<TreeNode>("/files", form);
  return res.data;
}

export async function moveDocument(path: string, folder: string): Promise<TreeNode> {
  const res = await api.post<TreeNode>("/files/move", { path, folder });
  return res.data;
}

export async function createDocumentFolder(path: string): Promise<TreeNode> {
  const res = await api.post<TreeNode>("/folders", { path });
  return res.data;
}

export async function deleteDocumentFile(path: string): Promise<string> {
  const res = await api.delete<{ message: string }>("/files", { params: { path } });
  return res.data.message;
}

export async function deleteDocumentFolder(path: string): Promise<string> {
  const res = await api.delete<{ message: string }>("/folders", { params: { path } });
  return res.data.message;
}

export async function fetchDownloadUrl(path: string): Promise<string> {
  const res = await api.get<{ url: string }>("/files/download", { params: { path } });
  return res.data.url;
}
