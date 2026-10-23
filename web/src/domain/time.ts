// Time is always read in the Festival's time zone (ADR-0005), never the
// browser's.

import type { DayKey, Festival, Instant } from "./model"

const formatters = new Map<string, Intl.DateTimeFormat>()

function formatter(timeZone: string, options: Intl.DateTimeFormatOptions) {
  const key = timeZone + JSON.stringify(options)
  let found = formatters.get(key)
  if (!found) {
    found = new Intl.DateTimeFormat("en-GB", { timeZone, ...options })
    formatters.set(key, found)
  }
  return found
}

function parts(instant: Instant, timeZone: string) {
  const all = formatter(timeZone, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(new Date(instant))
  const get = (type: Intl.DateTimeFormatPartTypes) =>
    Number(all.find((p) => p.type === type)?.value)
  return {
    year: get("year"),
    month: get("month"),
    day: get("day"),
    hour: get("hour"),
    minute: get("minute"),
  }
}

const pad = (n: number) => String(n).padStart(2, "0")

export function dayKey(instant: Instant, timeZone: string): DayKey {
  const p = parts(instant, timeZone)
  return `${p.year}-${pad(p.month)}-${pad(p.day)}`
}

/** "18:00" */
export function clock(instant: Instant, timeZone: string): string {
  const p = parts(instant, timeZone)
  return `${pad(p.hour)}:${pad(p.minute)}`
}

/** Minutes since local midnight; after-midnight screenings count past 24h. */
export function minuteOfDay(
  instant: Instant,
  day: DayKey,
  timeZone: string
): number {
  const p = parts(instant, timeZone)
  const shift = dayKey(instant, timeZone) > day ? 24 * 60 : 0
  return shift + p.hour * 60 + p.minute
}

/** Every day of the Festival, inclusive. */
export function festivalDays(festival: Festival): DayKey[] {
  const days: DayKey[] = []
  const cursor = new Date(`${festival.startDate}T12:00:00Z`)
  const end = new Date(`${festival.endDate}T12:00:00Z`)
  while (cursor <= end) {
    days.push(cursor.toISOString().slice(0, 10))
    cursor.setUTCDate(cursor.getUTCDate() + 1)
  }
  return days
}

/** "9" */
export function dayNumber(day: DayKey): string {
  return String(Number(day.slice(8, 10)))
}

/** "Fri" */
export function weekday(day: DayKey): string {
  return new Intl.DateTimeFormat("en-GB", {
    weekday: "short",
    timeZone: "UTC",
  }).format(new Date(`${day}T12:00:00Z`))
}

/** "Fri 10" */
export function shortDay(day: DayKey): string {
  return `${weekday(day)} ${dayNumber(day)}`
}

export function minutesBetween(start: Instant, end: Instant): number {
  return Math.round((Date.parse(end) - Date.parse(start)) / 60000)
}

export function isPast(instant: Instant, now: Date = new Date()): boolean {
  return Date.parse(instant) < now.getTime()
}
