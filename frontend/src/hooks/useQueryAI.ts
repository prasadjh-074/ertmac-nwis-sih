import { useMutation } from "@tanstack/react-query";
import { askNaturalLanguage, runStructuredQuery } from "@/api/query";
import type { QueryResponse, StructuredQuery } from "@/api/types";
import type { ApiMeta } from "@/api/client";

export interface Investigation {
  id: string;
  mode: "natural_language" | "structured";
  question: string;
  structured?: StructuredQuery;
  askedAt: string;
  response: QueryResponse;
  meta: ApiMeta;
}

const newId = () => Math.random().toString(36).slice(2, 10);

export function useAskAI() {
  return useMutation({
    mutationFn: async (question: string): Promise<Investigation> => {
      const { data, meta } = await askNaturalLanguage(question);
      return { id: newId(), mode: "natural_language", question, askedAt: new Date().toISOString(), response: data, meta };
    },
  });
}

export function useStructuredQuery() {
  return useMutation({
    mutationFn: async ({ query, label }: { query: StructuredQuery; label: string }): Promise<Investigation> => {
      const { data, meta } = await runStructuredQuery(query);
      return { id: newId(), mode: "structured", question: label, structured: query, askedAt: new Date().toISOString(), response: data, meta };
    },
  });
}
