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

/** What a Festival says about a film, in its own words and language. */
export interface EntryDetails {
  tagline: string | null
  /** Paragraphs separated by blank lines. */
  synopsis: string | null
  posterUrl: string | null
  /** A frame from the film, wider than tall. */
  stillUrl: string | null
  runtimeMinutes: number | null
  originalTitle: string | null
  director: string | null
  genre: string | null
  language: string | null
  subtitles: string | null
  ageLimit: string | null
  imdbUrl: string | null
}

export interface ProgrammeEntry {
  id: ProgrammeEntryId
  filmId: FilmId
  title: string
  year: number | null
  country: string | null
  url: string | null
  details: EntryDetails
  screenings: Screening[]
}

export interface Ticket {
  screening: Screening
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
  /** Withdrawn Screenings included, so it can be named. */
  screening: Screening | null
  programmeEntryId: ProgrammeEntryId | null
}

/** Two Programme Entries whose Screenings competed; the first was scheduled. */
export interface ComparisonPair {
  scheduledId: ProgrammeEntryId
  otherId: ProgrammeEntryId
}

export interface Comparison {
  preferredId: ProgrammeEntryId
  otherId: ProgrammeEntryId
}

/**
 * Settings that shape a User's Schedules for one Festival. Weights add to a
 * Screening's worth, 1 by default; a missing key means the default.
 */
export interface Preferences {
  /** Minutes to arrive before a Screening, unless its Venue has its own. */
  bufferMinutes: number
  venueBuffers: Readonly<Record<VenueId, number>>
  startDate: DayKey | null
  endDate: DayKey | null
  entryWeights: Readonly<Record<ProgrammeEntryId, number>>
  screeningWeights: Readonly<Record<ScreeningId, number>>
  /** Added to every Programme Entry of that year. */
  yearWeights: Readonly<Record<number, number>>
  /** Added to every Screening with an Event. */
  eventWeight: number
  /** Whether separately timed Events block time. */
  attendEvents: boolean
  transportMode: string | null
  /** How strongly Comparisons shift Programme Entry weights. */
  comparisonWeight: number
  comparisons: readonly Comparison[]
}

/** A signed-in User's accepted inputs for one Festival. */
export interface PlanningInputs {
  screeningCommitments: ScreeningId[]
  filmCommitments: ProgrammeEntryId[]
  excludedScreenings: ScreeningId[]
  excludedProgrammeEntries: ProgrammeEntryId[]
  preferences: Preferences
}

export interface Planning {
  festivalId: FestivalId
  activeSchedule: Schedule | null
  drafts: Draft[]
  inputs: PlanningInputs
  flags: Flag[]
  /** All the User's Tickets, any Festival; see `festivalTickets`. */
  tickets: Ticket[]
  suggestions: ComparisonPair[]
}

/** A change to one Preferences setting. A null value resets it. */
export type PreferenceItem =
  | {
      kind: "setProgrammeEntryWeight"
      programmeEntryId: ProgrammeEntryId
      weight: number | null
    }
  | {
      kind: "setScreeningWeight"
      screeningId: ScreeningId
      weight: number | null
    }
  | { kind: "setYearWeight"; year: number; weight: number | null }
  /** The general buffer, or with a Venue that Venue's. */
  | { kind: "setBuffer"; venueId: VenueId | null; minutes: number | null }
  /** Both null means every Festival Day. */
  | { kind: "setDateRange"; startDate: DayKey | null; endDate: DayKey | null }
  | { kind: "setEventWeight"; weight: number | null }
  | { kind: "setAttendEvents"; attend: boolean | null }
  | { kind: "setTransportMode"; mode: string | null }
  | { kind: "setComparisonWeight"; weight: number | null }

/** One change a Change Set proposes. */
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
  | PreferenceItem

export type ChangeSetItemKind = ChangeSetItem["kind"]
