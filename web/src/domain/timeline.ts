// Lay Screenings out on a day track: one row per festival day, x by time.

import type { DayKey, DraftDiff, Festival, Instant, Screening } from "./model"
import { addDays, dayKey, festivalDays, minuteOfDay } from "./time"

/** The hours a track shows, in minutes from its day's midnight; past 24h runs on. */
export interface Span {
  start: number
  end: number
}

/** For a week with nothing in it. */
export const DEFAULT_SPAN: Span = { start: 10 * 60, end: 25 * 60 }

/** Room left before the first start and after the last end. */
const MARGIN = 30

/** Every Screening, each on its own day, with a margin either side. */
export function fitSpan(festival: Festival, screenings: Screening[]): Span {
  if (screenings.length === 0) return DEFAULT_SPAN
  let start = Infinity
  let end = -Infinity
  for (const s of screenings) {
    const day = dayKey(s.startTime, festival.timeZone)
    start = Math.min(start, minuteOfDay(s.startTime, day, festival.timeZone))
    end = Math.max(end, minuteOfDay(s.endTime, day, festival.timeZone))
  }
  return { start: start - MARGIN, end: end + MARGIN }
}

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

const clamp = (n: number) => Math.min(1, Math.max(0, n))

/** 0..1 across the span. */
const across = (span: Span, minute: number) =>
  (minute - span.start) / (span.end - span.start)

export function layDays(
  festival: Festival,
  screenings: Screening[],
  span: Span
): DayRow[] {
  return [...byDay(festival, screenings)].map(([day, list]) => ({
    day,
    placed: list.map((screening) => {
      const start = minuteOfDay(screening.startTime, day, festival.timeZone)
      const end = minuteOfDay(screening.endTime, day, festival.timeZone)
      const left = clamp(across(span, start))
      return { screening, left, width: clamp(across(span, end)) - left }
    }),
  }))
}

/** At most this many hours between ticks before they thin out. */
const TICKS = 13

/** A tick on each whole hour in the span, thinned out on a long one. */
export function hourTicks(span: Span): { label: string; left: number }[] {
  const step = 60 * Math.ceil((span.end - span.start) / 60 / TICKS)
  const ticks = []
  for (let m = Math.ceil(span.start / 60) * 60; m <= span.end; m += step) {
    const hour = String((m / 60) % 24).padStart(2, "0")
    ticks.push({ label: hour, left: across(span, m) })
  }
  return ticks
}

/**
 * Where `now` falls on the tracks: its day and 0..1 across, or null when it
 * is off the span. Just after midnight it is still the evening before.
 */
export function nowOn(
  festival: Festival,
  span: Span,
  now: Instant
): { day: DayKey; left: number } | null {
  const today = dayKey(now, festival.timeZone)
  for (const day of [today, addDays(today, -1)]) {
    const minute = minuteOfDay(now, day, festival.timeZone)
    if (minute >= span.start && minute <= span.end)
      return { day, left: across(span, minute) }
  }
  return null
}

/** What a Draft does to a Screening: brings it In, takes it Out, or keeps it. */
export type Change = "in" | "out" | "kept"

export interface DiffRow {
  day: DayKey
  /** Something comes in or goes out on this day. */
  changed: boolean
  placed: (Placed & { change: Change })[]
}

/**
 * Lay a Draft's Schedule and its Out Screenings on one set of days, so the
 * Out ones line up under the day they leave.
 */
export function layDiff(
  festival: Festival,
  draft: Screening[],
  { added, removed }: Pick<DraftDiff, "added" | "removed">,
  span: Span
): DiffRow[] {
  const ins = new Set(added.map((s) => s.id))
  const outs = new Set(removed.map((s) => s.id))
  const changeOf = (s: Screening): Change =>
    outs.has(s.id) ? "out" : ins.has(s.id) ? "in" : "kept"
  return layDays(festival, [...draft, ...removed], span).map(
    ({ day, placed }) => {
      const tagged = placed.map((p) => ({
        ...p,
        change: changeOf(p.screening),
      }))
      return {
        day,
        changed: tagged.some((p) => p.change !== "kept"),
        placed: tagged,
      }
    }
  )
}
