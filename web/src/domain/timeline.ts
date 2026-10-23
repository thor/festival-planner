// Lay Screenings out on a day track: one row per festival day, x by time.

import type { DayKey, Festival, Screening } from "./model"
import { dayKey, festivalDays, minuteOfDay } from "./time"

export const TRACK_START = 10 * 60
export const TRACK_END = 25 * 60

export interface Placed {
  screening: Screening
  /** 0..1 across the track. */
  left: number
  width: number
}

export interface DayRow {
  day: DayKey
  placed: Placed[]
}

export function byDay(
  festival: Festival,
  screenings: Screening[]
): Map<DayKey, Screening[]> {
  const days = new Map<DayKey, Screening[]>(
    festivalDays(festival).map((d) => [d, []])
  )
  for (const s of screenings) {
    const key = dayKey(s.startTime, festival.timeZone)
    if (!days.has(key)) days.set(key, [])
    days.get(key)!.push(s)
  }
  for (const list of days.values()) {
    list.sort((a, b) => a.startTime.localeCompare(b.startTime))
  }
  return days
}

const span = TRACK_END - TRACK_START
const clamp = (n: number) => Math.min(1, Math.max(0, n))

export function layDays(festival: Festival, screenings: Screening[]): DayRow[] {
  return [...byDay(festival, screenings)].map(([day, list]) => ({
    day,
    placed: list.map((screening) => {
      const start = minuteOfDay(screening.startTime, day, festival.timeZone)
      const end = minuteOfDay(screening.endTime, day, festival.timeZone)
      const left = clamp((start - TRACK_START) / span)
      return {
        screening,
        left,
        width: clamp((end - TRACK_START) / span) - left,
      }
    }),
  }))
}

/** Hour ticks for the track, as labels and positions. */
export function hourTicks(): { label: string; left: number }[] {
  const ticks = []
  for (let m = TRACK_START; m <= TRACK_END; m += 120) {
    ticks.push({ label: String((m / 60) % 24), left: (m - TRACK_START) / span })
  }
  return ticks
}
