import type { SessionPort } from "@/domain/ports"

const KEY = "festival-planner.token"

function read(): string | null {
  try {
    return localStorage.getItem(KEY)
  } catch {
    return null
  }
}

function write(token: string | null) {
  try {
    if (token === null) localStorage.removeItem(KEY)
    else localStorage.setItem(KEY, token)
  } catch {
    // Storage blocked: the token lives for this page only.
  }
}

/** A bearer token kept in localStorage. */
export function browserSession(): SessionPort {
  let current = read()
  const listeners = new Set<() => void>()
  const set = (token: string | null) => {
    current = token
    write(token)
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
