"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  adjustProductStock,
  createProduct,
  deleteProduct,
  fetchProducts,
  updateProduct,
} from "@/lib/api-client";
import type { ProductInput, ProductRow } from "@/lib/types";

const productsKey = ["products"] as const;

export function useProducts(initialData: ProductRow[]) {
  return useQuery({
    queryKey: productsKey,
    queryFn: fetchProducts,
    initialData,
    refetchInterval: 30_000,
  });
}

export function useProductMutations() {
  const queryClient = useQueryClient();

  const createMutation = useMutation({
    mutationFn: (payload: ProductInput) => createProduct(payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: productsKey });
      await queryClient.invalidateQueries({ queryKey: ["owner-dashboard", "summary"] });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ productId, payload }: { productId: string; payload: ProductInput }) =>
      updateProduct(productId, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: productsKey });
      await queryClient.invalidateQueries({ queryKey: ["owner-dashboard", "summary"] });
    },
  });

  const stockMutation = useMutation({
    mutationFn: ({ productId, delta, reason }: { productId: string; delta: number; reason: string }) =>
      adjustProductStock(productId, delta, reason),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: productsKey });
      await queryClient.invalidateQueries({ queryKey: ["owner-dashboard", "summary"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (productId: string) => deleteProduct(productId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: productsKey });
      await queryClient.invalidateQueries({ queryKey: ["owner-dashboard", "summary"] });
    },
  });

  return {
    createProduct: async (payload: ProductInput) => {
      await createMutation.mutateAsync(payload);
    },
    updateProduct: async (productId: string, payload: ProductInput) => {
      await updateMutation.mutateAsync({ productId, payload });
    },
    adjustStock: async (productId: string, delta: number, reason: string) => {
      await stockMutation.mutateAsync({ productId, delta, reason });
    },
    deleteProduct: async (productId: string) => {
      await deleteMutation.mutateAsync(productId);
    },
    isCreating: createMutation.isPending,
    isUpdating: updateMutation.isPending,
    isAdjusting: stockMutation.isPending,
    isDeleting: deleteMutation.isPending,
  };
}
