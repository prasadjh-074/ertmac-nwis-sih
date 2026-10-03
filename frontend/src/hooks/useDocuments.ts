import { useMutation, useQueries, useQuery } from "@tanstack/react-query";
import { getDocumentMetadata, searchDocuments } from "@/api/documents";
import type { DocumentSearchRequest } from "@/api/types";

export function useDocumentSearch() {
  return useMutation({ mutationFn: (req: DocumentSearchRequest) => searchDocuments(req) });
}

export function useDocumentMetadata(documentId: string | null) {
  return useQuery({
    queryKey: ["documents", "meta", documentId],
    queryFn: () => getDocumentMetadata(documentId!),
    enabled: !!documentId,
  });
}

export function useDocumentsMetadata(ids: string[]) {
  return useQueries({
    queries: ids.map((id) => ({ queryKey: ["documents", "meta", id], queryFn: () => getDocumentMetadata(id) })),
  });
}
