"use client";
/**
 * Client providers for the whole app (mounted once in app/layout.tsx):
 * TanStack Query · toasts · login prompt · realtime WebSocket bridge (logged-in users only).
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { isApiError } from "@/lib/api/errors";
import { useMe } from "@/lib/auth/hooks";
import { useRealtime } from "@/lib/realtime/useRealtime";
import { LoginPromptProvider } from "@/components/auth/LoginPrompt";
import { ToastProvider, useToast } from "@/components/ui/Toast";

export function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        gcTime: 5 * 60_000,
        refetchOnWindowFocus: true,
        // GETs are already retried inside the API client (network/502-504); here only 429/500 get one more try,
        // 4xx never (they will not succeed on repeat)
        retry: (count, err) => (isApiError(err) ? (err.status === 429 || err.status === 500) && count < 1 : count < 1),
        retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 8000),
      },
      mutations: { retry: false },
    },
  });
}

function RealtimeBridge() {
  const { me } = useMe();
  const toast = useToast();
  useRealtime({
    enabled: Boolean(me),
    onNotification: (n) => toast.info(n.title),
  });
  return null;
}

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(makeQueryClient);
  return (
    <QueryClientProvider client={client}>
      <ToastProvider>
        <LoginPromptProvider>
          <RealtimeBridge />
          {children}
        </LoginPromptProvider>
      </ToastProvider>
    </QueryClientProvider>
  );
}
