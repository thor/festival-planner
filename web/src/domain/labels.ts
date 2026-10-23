// Terse words for domain values. Plain text, no markup.

import { verbOf, type ItemVerb } from "./change-set"
import type { ChangeSetItem, ProgrammeEntry, Screening, Venue } from "./model"
import {
  comparisonScale,
  defaultPreferences,
  entryScale,
  interestOf,
  offsetScale,
  type Interest,
  type Scale,
} from "./preferences"
import type { LetGoReason } from "./tickets"
import type { Change } from "./timeline"
import { clock, dayKey, shortDay } from "./time"

export interface Lookup {
  entry(id: string): ProgrammeEntry | undefined
  screening(id: string): Screening | undefined
  venue(id: string): Venue | undefined
  timeZone: string
}

export function lookupOf(entries: ProgrammeEntry[], timeZone: string): Lookup {
  const e = new Map(entries.map((x) => [x.id as string, x]))
  const s = new Map(
    entries.flatMap((x) => x.screenings).map((x) => [x.id as string, x])
  )
  const v = new Map([...s.values()].map((x) => [x.venue.id as string, x.venue]))
  return {
    entry: (id) => e.get(id),
    screening: (id) => s.get(id),
    venue: (id) => v.get(id),
    timeZone,
  }
}

export function when(s: Screening, timeZone: string): string {
  return `${shortDay(dayKey(s.startTime, timeZone))} ${clock(s.startTime, timeZone)}`
}

export const letGoWord: Record<LetGoReason, string> = {
  withdrawn: "Withdrawn",
  notScheduled: "Not scheduled",
}

export const verbWord: Record<ItemVerb, string> = {
  commit: "Commit",
  release: "Release",
  exclude: "Exclude",
  include: "Include",
  compare: "Compare",
  interest: "Interest",
  buffer: "Arrive early",
  days: "Days",
  events: "Events",
  transport: "Transport",
}

export const interestWord: Record<Interest, string> = {
  less: "Less",
  usual: "Usual",
  more: "More",
  most: "Most",
}

/** "more", or "usual" for a reset. */
function step(weight: number | null, scale: Scale): string {
  return interestWord[
    weight === null ? "usual" : interestOf(weight, scale)
  ].toLowerCase()
}

/** "Fri 30 to Mon 2", or "Every day" when there are no bounds. */
export function dayRange(start: string | null, end: string | null): string {
  if (start && end)
    return start === end
      ? `${shortDay(start)} only`
      : `${shortDay(start)} to ${shortDay(end)}`
  if (start) return `From ${shortDay(start)}`
  if (end) return `Until ${shortDay(end)}`
  return "Every day"
}

/** What an item is about: a title, a time, or a value. */
export function subjectOf(item: ChangeSetItem, lookup: Lookup): string {
  const title = (id: string) => lookup.entry(id)?.title ?? "Unknown film"
  const screening = (id: string) => {
    const s = lookup.screening(id)
    return s ? `${s.title}, ${when(s, lookup.timeZone)}` : "Unknown screening"
  }
  switch (item.kind) {
    case "addScreeningCommitment":
    case "releaseScreeningCommitment":
    case "addExcludedScreening":
    case "removeExcludedScreening":
      return screening(item.screeningId)
    case "addFilmCommitment":
    case "releaseFilmCommitment":
    case "addExcludedProgrammeEntry":
    case "removeExcludedProgrammeEntry":
      return title(item.programmeEntryId)
    case "recordComparison":
      return `${title(item.preferredId)} over ${title(item.otherId)}`
    case "setProgrammeEntryWeight":
      return `${title(item.programmeEntryId)}, ${step(item.weight, entryScale)}`
    case "setScreeningWeight":
      return `${screening(item.screeningId)}, ${step(item.weight, entryScale)}`
    case "setYearWeight":
      return `Films from ${item.year}, ${step(item.weight, offsetScale)}`
    case "setEventWeight":
      return `Screenings with events, ${step(item.weight, offsetScale)}`
    case "setComparisonWeight":
      return `Comparisons, ${step(item.weight, comparisonScale)}`
    case "setBuffer": {
      if (item.venueId) {
        const where = lookup.venue(item.venueId)?.name ?? "Unknown venue"
        return `${where}, ${item.minutes === null ? "usual" : `${item.minutes} min`}`
      }
      return `${item.minutes ?? defaultPreferences.bufferMinutes} min`
    }
    case "setDateRange":
      return dayRange(item.startDate, item.endDate)
    case "setAttendEvents":
      return item.attend ? "Stay for events" : "Skip separate events"
    case "setTransportMode":
      return item.mode ?? "Usual transport"
  }
}

export function describeItem(item: ChangeSetItem, lookup: Lookup) {
  const verb = verbOf(item)
  return { verb, word: verbWord[verb], subject: subjectOf(item, lookup) }
}

export function signed(n: number): string {
  const r = Math.round(n * 10) / 10
  return r > 0 ? `+${r}` : r < 0 ? `−${-r}` : "0"
}

/** What a Draft does to a Screening; kept needs no word. */
export const changeWord: Record<Exclude<Change, "kept">, string> = {
  in: "In",
  out: "Out",
}

/** "1 h 18 min", "45 min", "2 h". */
export function runtimeWord(minutes: number): string {
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  if (!h) return `${m} min`
  return m ? `${h} h ${m} min` : `${h} h`
}

/**
 * A Festival's description as paragraphs, and who wrote it: Festivals often
 * sign it with a short name on a line of its own.
 */
export function splitSynopsis(text: string | null): {
  paragraphs: string[]
  credit: string | null
} {
  const paragraphs = (text ?? "")
    .split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter(Boolean)
  const last = paragraphs.at(-1)
  const signed =
    paragraphs.length > 1 &&
    !!last &&
    last.length <= 40 &&
    !/[.!?:]$/.test(last)
  return {
    paragraphs: signed ? paragraphs.slice(0, -1) : paragraphs,
    credit: signed ? last! : null,
  }
}
