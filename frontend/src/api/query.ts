import { apiFetchWithMeta } from "./client";
import type { QueryResponse, StructuredQuery } from "./types";

export const askNaturalLanguage = (question: string) =>
  apiFetchWithMeta<QueryResponse>("/query", { method: "POST", body: { question }, timeoutMs: 120_000 });

export const runStructuredQuery = (structured_query: StructuredQuery) =>
  apiFetchWithMeta<QueryResponse>("/query/structured", { method: "POST", body: { structured_query }, timeoutMs: 120_000 });
