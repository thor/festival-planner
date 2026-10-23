// GraphQL shapes to domain values and back. The only place that knows both.

import type { ResultOf, VariablesOf } from "gql.tada"

import type {
  ChangeSetItem,
  Draft,
  DraftId,
  Festival,
  FestivalId,
  FilmId,
  Flag,
  PlanningInputs,
  Preferences,
  ProgrammeEntry,
  ProgrammeEntryId,
  Schedule,
  ScheduleId,
  Screening,
  ScreeningId,
  VenueId,
} from "@/domain/model"

import type {
  ChangeSetFields,
  CreateDraftMutation,
  DraftFields,
  EntryFields,
  FestivalFields,
  PlanningQuery,
  PreferencesFields,
  ScreeningFields,
} from "./documents"

type FestivalData = ResultOf<typeof FestivalFields>
type ScreeningData = ResultOf<typeof ScreeningFields>
type EntryData = ResultOf<typeof EntryFields>
type ChangeSetData = ResultOf<typeof ChangeSetFields>
type DraftData = ResultOf<typeof DraftFields>
type PreferencesData = ResultOf<typeof PreferencesFields>
type PlanningData = NonNullable<
  NonNullable<ResultOf<typeof PlanningQuery>["viewer"]>["planning"]
>

export function festivalOf(f: FestivalData): Festival {
  return { ...f, id: f.id as FestivalId }
}

export function screeningOf(s: ScreeningData): Screening {
  return {
    id: s.id as ScreeningId,
    programmeEntryId: s.programmeEntry.id as ProgrammeEntryId,
    title: s.programmeEntry.title,
    startTime: s.startTime,
    endTime: s.endTime,
    venue: { id: s.venue.id as VenueId, name: s.venue.name },
    auditorium: s.auditorium,
    ticketUrl: s.ticketUrl,
    events: s.events,
    withdrawn: s.withdrawn,
  }
}

export function entryOf(e: EntryData): ProgrammeEntry {
  return {
    id: e.id as ProgrammeEntryId,
    filmId: e.film.id as FilmId,
    title: e.title,
    year: e.year,
    country: e.country,
    url: e.url,
    screenings: e.screenings.map(screeningOf),
  }
}

export function itemOf(i: ChangeSetData): ChangeSetItem {
  const s = (x: { screening: { id: string } }) => x.screening.id as ScreeningId
  const e = (x: { programmeEntry: { id: string } }) =>
    x.programmeEntry.id as ProgrammeEntryId
  switch (i.__typename) {
    case "AddScreeningCommitment":
      return { kind: "addScreeningCommitment", screeningId: s(i) }
    case "ReleaseScreeningCommitment":
      return { kind: "releaseScreeningCommitment", screeningId: s(i) }
    case "AddExcludedScreening":
      return { kind: "addExcludedScreening", screeningId: s(i) }
    case "RemoveExcludedScreening":
      return { kind: "removeExcludedScreening", screeningId: s(i) }
    case "AddFilmCommitment":
      return { kind: "addFilmCommitment", programmeEntryId: e(i) }
    case "ReleaseFilmCommitment":
      return { kind: "releaseFilmCommitment", programmeEntryId: e(i) }
    case "AddExcludedProgrammeEntry":
      return { kind: "addExcludedProgrammeEntry", programmeEntryId: e(i) }
    case "RemoveExcludedProgrammeEntry":
      return { kind: "removeExcludedProgrammeEntry", programmeEntryId: e(i) }
    case "RecordComparison":
      return {
        kind: "recordComparison",
        preferredId: i.preferred.id as ProgrammeEntryId,
        otherId: i.other.id as ProgrammeEntryId,
      }
    case "SetProgrammeEntryWeight":
      return {
        kind: "setProgrammeEntryWeight",
        programmeEntryId: e(i),
        weight: i.weight,
      }
    case "SetScreeningWeight":
      return { kind: "setScreeningWeight", screeningId: s(i), weight: i.weight }
    case "SetYearWeight":
      return { kind: "setYearWeight", year: i.year, weight: i.weight }
    case "SetBuffer":
      return {
        kind: "setBuffer",
        venueId: (i.venue?.id ?? null) as VenueId | null,
        minutes: i.minutes,
      }
    case "SetDateRange":
      return {
        kind: "setDateRange",
        startDate: i.startDate,
        endDate: i.endDate,
      }
    case "SetEventWeight":
      return { kind: "setEventWeight", weight: i.weight }
    case "SetAttendEvents":
      return { kind: "setAttendEvents", attend: i.attend }
    case "SetTransportMode":
      return { kind: "setTransportMode", mode: i.mode }
    case "SetComparisonWeight":
      return { kind: "setComparisonWeight", weight: i.weight }
  }
}

type ItemInput = NonNullable<
  VariablesOf<typeof CreateDraftMutation>["input"]["changeSet"]
>[number]

export function itemInputOf(item: ChangeSetItem): ItemInput {
  switch (item.kind) {
    case "addScreeningCommitment":
      return { addScreeningCommitment: { screeningId: item.screeningId } }
    case "releaseScreeningCommitment":
      return { releaseScreeningCommitment: { screeningId: item.screeningId } }
    case "addExcludedScreening":
      return { addExcludedScreening: { screeningId: item.screeningId } }
    case "removeExcludedScreening":
      return { removeExcludedScreening: { screeningId: item.screeningId } }
    case "addFilmCommitment":
      return { addFilmCommitment: { programmeEntryId: item.programmeEntryId } }
    case "releaseFilmCommitment":
      return {
        releaseFilmCommitment: { programmeEntryId: item.programmeEntryId },
      }
    case "addExcludedProgrammeEntry":
      return {
        addExcludedProgrammeEntry: { programmeEntryId: item.programmeEntryId },
      }
    case "removeExcludedProgrammeEntry":
      return {
        removeExcludedProgrammeEntry: {
          programmeEntryId: item.programmeEntryId,
        },
      }
    case "recordComparison":
      return {
        recordComparison: {
          preferredId: item.preferredId,
          otherId: item.otherId,
        },
      }
    case "setProgrammeEntryWeight":
      return {
        setProgrammeEntryWeight: {
          programmeEntryId: item.programmeEntryId,
          weight: item.weight,
        },
      }
    case "setScreeningWeight":
      return {
        setScreeningWeight: {
          screeningId: item.screeningId,
          weight: item.weight,
        },
      }
    case "setYearWeight":
      return { setYearWeight: { year: item.year, weight: item.weight } }
    case "setBuffer":
      return { setBuffer: { venueId: item.venueId, minutes: item.minutes } }
    case "setDateRange":
      return {
        setDateRange: { startDate: item.startDate, endDate: item.endDate },
      }
    case "setEventWeight":
      return { setEventWeight: { weight: item.weight } }
    case "setAttendEvents":
      return { setAttendEvents: { attend: item.attend } }
    case "setTransportMode":
      return { setTransportMode: { mode: item.mode } }
    case "setComparisonWeight":
      return { setComparisonWeight: { weight: item.weight } }
  }
}

export function draftOf(d: DraftData, diff: Draft["diff"] = null): Draft {
  return {
    id: d.id as DraftId,
    festivalId: d.festival.id as FestivalId,
    status: d.status,
    stale: d.stale,
    changeSet: d.changeSet.map(itemOf),
    screenings: d.screenings.map((s) => screeningOf(s.screening)),
    score: d.score,
    reasons: d.reasons,
    notes: d.notes,
    createdAt: d.createdAt,
    diff,
  }
}

export function scheduleOf(s: {
  id: string
  number: number
  score: number
  acceptedAt: string
  screenings: ScreeningData[]
}): Schedule {
  return {
    ...s,
    id: s.id as ScheduleId,
    screenings: s.screenings.map(screeningOf),
  }
}

export function flagOf(f: PlanningData["flags"][number]): Flag {
  return {
    kind: f.kind,
    message: f.message,
    screening: f.screening ? screeningOf(f.screening) : null,
    programmeEntryId: (f.programmeEntry?.id ?? null) as ProgrammeEntryId | null,
  }
}

/** A list of weights as a record by key. */
function byKey<K extends string | number, T>(
  list: readonly T[],
  key: (t: T) => K,
  value: (t: T) => number
): Record<K, number> {
  return Object.fromEntries(list.map((t) => [key(t), value(t)])) as Record<
    K,
    number
  >
}

export function preferencesOf(p: PreferencesData): Preferences {
  return {
    bufferMinutes: p.bufferMinutes,
    venueBuffers: byKey(
      p.venueBuffers,
      (b) => b.venue.id as VenueId,
      (b) => b.minutes
    ),
    startDate: p.startDate,
    endDate: p.endDate,
    entryWeights: byKey(
      p.programmeEntryWeights,
      (w) => w.programmeEntry.id as ProgrammeEntryId,
      (w) => w.weight
    ),
    screeningWeights: byKey(
      p.screeningWeights,
      (w) => w.screening.id as ScreeningId,
      (w) => w.weight
    ),
    yearWeights: byKey(
      p.yearWeights,
      (w) => w.year,
      (w) => w.weight
    ),
    eventWeight: p.eventWeight,
    attendEvents: p.attendEvents,
    transportMode: p.transportMode,
    comparisonWeight: p.comparisonWeight,
    comparisons: p.comparisons.map((c) => ({
      preferredId: c.preferred.id as ProgrammeEntryId,
      otherId: c.other.id as ProgrammeEntryId,
    })),
  }
}

export function inputsOf(i: PlanningData["inputs"]): PlanningInputs {
  return {
    preferences: preferencesOf(i.preferences),
    screeningCommitments: i.screeningCommitments.map(
      (s) => s.id as ScreeningId
    ),
    filmCommitments: i.filmCommitments.map((e) => e.id as ProgrammeEntryId),
    excludedScreenings: i.excludedScreenings.map((s) => s.id as ScreeningId),
    excludedProgrammeEntries: i.excludedProgrammeEntries.map(
      (e) => e.id as ProgrammeEntryId
    ),
  }
}
