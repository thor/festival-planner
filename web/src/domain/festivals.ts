// Festivals as a list: which are on, which are ahead, and their dates.

import type { DayKey, Festival } from "./model"
import { dayKey } from "./time"

export type Phase = "now" | "ahead" | "over"

/** Today in the Festival's own time zone (ADR-0005). */
const todayIn = (f: Festival, now: Date): DayKey =>
  dayKey(now.toISOString(), f.timeZone)

export function phaseOf(f: Festival, now: Date = new Date()): Phase {
  const today = todayIn(f, now)
  if (today < f.startDate) return "ahead"
  if (today > f.endDate) return "over"
  return "now"
}

const rank: Record<Phase, number> = { now: 0, ahead: 1, over: 2 }

/** On now first, then the soonest ahead, then the most recently over. */
export function festivalsInOrder(
  festivals: Festival[],
  now: Date = new Date()
): Festival[] {
  return [...festivals].sort((a, b) => {
    const pa = phaseOf(a, now)
    const pb = phaseOf(b, now)
    if (pa !== pb) return rank[pa] - rank[pb]
    const byStart = a.startDate.localeCompare(b.startDate)
    return pa === "over" ? -byStart : byStart
  })
}

const month = (day: DayKey) =>
  new Intl.DateTimeFormat("en-GB", { month: "long", timeZone: "UTC" }).format(
    new Date(`${day}T12:00:00Z`)
  )
const date = (day: DayKey) => Number(day.slice(8, 10))
const year = (day: DayKey) => day.slice(0, 4)

/** "6–16 November 2026", widening only as far as the dates need. */
export function dateSpan(f: Festival): string {
  const { startDate: s, endDate: e } = f
  if (s === e) return `${date(s)} ${month(s)} ${year(s)}`
  if (year(s) !== year(e))
    return `${date(s)} ${month(s)} ${year(s)} – ${date(e)} ${month(e)} ${year(e)}`
  if (month(s) !== month(e))
    return `${date(s)} ${month(s)} – ${date(e)} ${month(e)} ${year(e)}`
  return `${date(s)}–${date(e)} ${month(e)} ${year(e)}`
}
