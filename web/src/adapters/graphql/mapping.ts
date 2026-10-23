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
  ScreeningFields,
} from "./documents"

type FestivalData = ResultOf<typeof FestivalFields>
type ScreeningData = ResultOf<typeof ScreeningFields>
type EntryData = ResultOf<typeof EntryFields>
type ChangeSetData = ResultOf<typeof ChangeSetFields>
type DraftData = ResultOf<typeof DraftFields>
type PlanningData = NonNullable<NonNullable<ResultOf<typeof PlanningQuery>["viewer"]>["planning"]>

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
  const e = (x: { programmeEntry: { id: string } }) => x.programmeEntry.id as ProgrammeEntryId
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
    case "SetBuffer":
      return i.venue ? { kind: "other", label: "Venue buffer" } : { kind: "setBuffer", minutes: i.minutes }
    default:
      return { kind: "other", label: i.__typename }
  }
}

type ItemInput = NonNullable<VariablesOf<typeof CreateDraftMutation>["input"]["changeSet"]>[number]

/** Items the API takes. "other" items came from the API and are not sent back. */
export function itemInputOf(item: ChangeSetItem): ItemInput | null {
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
      return { releaseFilmCommitment: { programmeEntryId: item.programmeEntryId } }
    case "addExcludedProgrammeEntry":
      return { addExcludedProgrammeEntry: { programmeEntryId: item.programmeEntryId } }
    case "removeExcludedProgrammeEntry":
      return { removeExcludedProgrammeEntry: { programmeEntryId: item.programmeEntryId } }
    case "recordComparison":
      return { recordComparison: { preferredId: item.preferredId, otherId: item.otherId } }
    case "setBuffer":
      return { setBuffer: { minutes: item.minutes } }
    case "other":
      return null
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
  return { ...s, id: s.id as ScheduleId, screenings: s.screenings.map(screeningOf) }
}

export function flagOf(f: PlanningData["flags"][number]): Flag {
  return {
    kind: f.kind,
    message: f.message,
    screening: f.screening ? screeningOf(f.screening) : null,
    programmeEntryId: (f.programmeEntry?.id ?? null) as ProgrammeEntryId | null,
  }
}

export function inputsOf(i: PlanningData["inputs"]) {
  return {
    bufferMinutes: i.preferences.bufferMinutes,
    screeningCommitments: i.screeningCommitments.map((s) => s.id as ScreeningId),
    filmCommitments: i.filmCommitments.map((e) => e.id as ProgrammeEntryId),
    excludedScreenings: i.excludedScreenings.map((s) => s.id as ScreeningId),
    excludedProgrammeEntries: i.excludedProgrammeEntries.map((e) => e.id as ProgrammeEntryId),
  }
}
