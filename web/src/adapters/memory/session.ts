import type { SessionPort } from "@/domain/ports"

/** A session that starts signed in, kept in memory only. */
export function memorySession(initial: string | null = "sample"): SessionPort {
  let current = initial
  const listeners = new Set<() => void>()
  const set = (token: string | null) => {
    current = token
    listeners.forEach((l) => l())
  }
  return {
    token: () => current,
    signIn: (token) => set(token.trim() || null),
    signOut: () => set(null),
    subscribe(listener) {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
  }
}
