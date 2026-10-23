import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { createContext, use, type ReactNode } from "react"

import type { Ports } from "@/domain/ports"

const PortsContext = createContext<Ports | null>(null)

export function PortsProvider({
  ports,
  children,
}: {
  ports: Ports
  children: ReactNode
}) {
  return (
    <PortsContext value={ports}>
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </PortsContext>
  )
}

export function usePorts(): Ports {
  const ports = use(PortsContext)
  if (!ports) throw new Error("PortsProvider missing")
  return ports
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false },
  },
})
