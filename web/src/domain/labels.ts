// Terse words for domain values. Plain text, no markup.

import { verbOf, type ItemVerb } from "./change-set"
import type { ChangeSetItem, ProgrammeEntry, Screening } from "./model"
import type { LetGoReason } from "./tickets"
import { clock, dayKey, shortDay } from "./time"

export interface Lookup {
  entry(id: string): ProgrammeEntry | undefined
  screening(id: string): Screening | undefined
  timeZone: string
}

export function lookupOf(entries: ProgrammeEntry[], timeZone: string): Lookup {
  const e = new Map(entries.map((x) => [x.id as string, x]))
  const s = new Map(entries.flatMap((x) => x.screenings).map((x) => [x.id as string, x]))
  return { entry: (id) => e.get(id), screening: (id) => s.get(id), timeZone }
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
  prefer: "Prefer",
  buffer: "Buffer",
  other: "Change",
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
    case "setBuffer":
      return item.minutes === null ? "Default" : `${item.minutes} min`
    case "other":
      return item.label
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
