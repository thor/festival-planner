// Domain values, named as in GLOSSARY.md. Ids are opaque global ids.

type Id<Brand extends string> = string & { readonly __brand: Brand }

export type FestivalId = Id<"Festival">
export type ProgrammeEntryId = Id<"ProgrammeEntry">
export type ScreeningId = Id<"Screening">
export type VenueId = Id<"Venue">
export type DraftId = Id<"Draft">
export type ScheduleId = Id<"Schedule">
export type FilmId = Id<"Film">

/** ISO date with offset, as the API sends it. */
export type Instant = string
/** YYYY-MM-DD in the Festival's time zone. */
export type DayKey = string

export interface Festival {
  id: FestivalId
  slug: string
  name: string
  startDate: DayKey
  endDate: DayKey
  timeZone: string
}

export interface Venue {
  id: VenueId
  name: string
}

export interface Event {
  description: string
  startTime: Instant | null
  endTime: Instant | null
}

export interface Screening {
  id: ScreeningId
  programmeEntryId: ProgrammeEntryId
  title: string
  startTime: Instant
  endTime: Instant
  venue: Venue
  auditorium: string | null
  ticketUrl: string | null
  events: Event[]
  withdrawn: boolean
}

export interface ProgrammeEntry {
  id: ProgrammeEntryId
  filmId: FilmId
  title: string
  year: number | null
  country: string | null
  url: string | null
  screenings: Screening[]
}

export interface Ticket {
  screeningId: ScreeningId
  exchangeable: boolean
  refundable: boolean
}

export interface Schedule {
  id: ScheduleId
  number: number
  score: number
  acceptedAt: Instant
  screenings: Screening[]
}

export type DraftStatus = "SOLVING" | "READY" | "INFEASIBLE" | "FAILED"

export interface DraftDiff {
  scoreDelta: number
  added: Screening[]
  removed: Screening[]
  droppedTickets: Screening[]
}

export interface Draft {
  id: DraftId
  festivalId: FestivalId
  status: DraftStatus
  stale: boolean
  changeSet: ChangeSetItem[]
  screenings: Screening[]
  score: number
  reasons: string[]
  notes: string[]
  createdAt: Instant
  diff: DraftDiff | null
}

export type FlagKind =
  | "WITHDRAWN_COMMITMENT"
  | "WITHDRAWN_TICKET"
  | "UNSCHEDULED_TICKET"
  | "WITHDRAWN_IN_SCHEDULE"

export interface Flag {
  kind: FlagKind
  message: string
  screeningId: ScreeningId | null
  programmeEntryId: ProgrammeEntryId | null
}

export interface ComparisonPair {
  scheduled: ProgrammeEntry
  other: ProgrammeEntry
}

/** A signed-in User's accepted inputs for one Festival. */
export interface PlanningInputs {
  screeningCommitments: ScreeningId[]
  filmCommitments: ProgrammeEntryId[]
  excludedScreenings: ScreeningId[]
  excludedProgrammeEntries: ProgrammeEntryId[]
  bufferMinutes: number
}

export interface Planning {
  festivalId: FestivalId
  activeSchedule: Schedule | null
  drafts: Draft[]
  inputs: PlanningInputs
  flags: Flag[]
  tickets: Ticket[]
  suggestions: ComparisonPair[]
}

/**
 * One change a Change Set proposes. The subset the concepts edit; the API
 * has more kinds (weights, buffers, date range, events, transport).
 */
export type ChangeSetItem =
  | { kind: "addScreeningCommitment"; screeningId: ScreeningId }
  | { kind: "releaseScreeningCommitment"; screeningId: ScreeningId }
  | { kind: "addFilmCommitment"; programmeEntryId: ProgrammeEntryId }
  | { kind: "releaseFilmCommitment"; programmeEntryId: ProgrammeEntryId }
  | { kind: "addExcludedScreening"; screeningId: ScreeningId }
  | { kind: "removeExcludedScreening"; screeningId: ScreeningId }
  | { kind: "addExcludedProgrammeEntry"; programmeEntryId: ProgrammeEntryId }
  | { kind: "removeExcludedProgrammeEntry"; programmeEntryId: ProgrammeEntryId }
  | {
      kind: "recordComparison"
      preferredId: ProgrammeEntryId
      otherId: ProgrammeEntryId
    }
  | { kind: "setBuffer"; minutes: number | null }
  | { kind: "other"; label: string }

export type ChangeSetItemKind = ChangeSetItem["kind"]
