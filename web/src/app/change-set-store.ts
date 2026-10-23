// Pending Change Sets, one per Festival, shared across pages. The rules live
// in domain/change-set; this only holds the value.

import { useCallback, useSyncExternalStore } from "react"

import type { ChangeSet } from "@/domain/change-set"
import type { FestivalId } from "@/domain/model"

const sets = new Map<FestivalId, ChangeSet>()
const listeners = new Set<() => void>()
const empty: ChangeSet = []

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function usePendingChangeSet(festivalId: FestivalId | undefined) {
  const set = useSyncExternalStore(
    subscribe,
    () => (festivalId && sets.get(festivalId)) || empty
  )
  const update = useCallback(
    (change: (set: ChangeSet) => ChangeSet) => {
      if (!festivalId) return
      sets.set(festivalId, change(sets.get(festivalId) ?? empty))
      listeners.forEach((l) => l())
    },
    [festivalId]
  )
  return [set, update] as const
}
