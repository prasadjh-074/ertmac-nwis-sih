import { apiFetch } from "./client";
import type { DocumentMetadata, DocumentSearchRequest, DocumentSearchResponse } from "./types";

export const searchDocuments = (req: DocumentSearchRequest) =>
  apiFetch<DocumentSearchResponse>("/documents/search", { method: "POST", body: req, timeoutMs: 120_000 });

export const getDocumentMetadata = (documentId: string) =>
  apiFetch<DocumentMetadata>(`/documents/${encodeURIComponent(documentId)}`);
