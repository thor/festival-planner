import { useEffect, useState } from "react"

import type { Instant } from "@/domain/model"

/** The current instant, refreshed every minute. */
export function useNow(): Instant {
  const [now, setNow] = useState(() => new Date().toISOString())
  useEffect(() => {
    const id = setInterval(() => setNow(new Date().toISOString()), 60_000)
    return () => clearInterval(id)
  }, [])
  return now
}
