// What views render. Plain data and callbacks; no domain types leak through.

import type { ItemVerb } from "@/domain/change-set"

export type Load<T> =
  | { state: "loading" }
  | { state: "missing"; message: string }
  | { state: "ready"; value: T }

export interface FestivalVM {
  slug: string
  name: string
  href: string
  dates: string
  phase: "now" | "ahead" | "over"
}

export interface Marks {
  committed: boolean
  excluded: boolean
  pending: boolean
}

export interface ScreeningVM {
  id: string
  day: string
  time: string
  venue: string
  /** A number or a name; null when the programme does not say. */
  auditorium: string | null
  withdrawn: boolean
  past: boolean
  /** In the Active Schedule. */
  scheduled: boolean
  ticket: boolean
  /** Where to buy a ticket; null when one is held, there is nowhere, or it is too late. */
  buyHref: string | null
  event: string | null
  marks: Marks
  onCommit?: () => void
  onExclude?: () => void
  onTicket?: () => void
}

export interface EntryVM {
  id: string
  title: string
  href: string
  meta: string[]
  marks: Marks
  screenings: ScreeningVM[]
  onCommit?: () => void
  onExclude?: () => void
}

export interface DayVM {
  key: string
  number: string
  weekday: string
  href: string
  current: boolean
}

export interface ProgrammeVM {
  festival: string
  days: DayVM[]
  allHref: string
  allCurrent: boolean
  entries: EntryVM[]
}

export interface FilmVM {
  title: string
  /** The selected viewing, while it can be bought; null once a ticket is held. */
  buy: ScreeningVM | null
  meta: string[]
  url: string | null
  entry: EntryVM
  backHref: string
}

export interface BlockVM {
  id: string
  title: string
  time: string
  end: string
  venue: string
  /** A number or a name; null when the programme does not say. */
  auditorium: string | null
  href: string
  left: number
  width: number
  ticket: boolean
  committed: boolean
  withdrawn: boolean
}

export interface ScheduleDayVM {
  key: string
  number: string
  weekday: string
  blocks: BlockVM[]
}

export interface ScheduleVM {
  number: number | null
  count: number
  days: ScheduleDayVM[]
  ticks: { label: string; left: number }[]
  /** Tickets to let go, counted here and listed on the Tickets page. */
  letGo: number
  ticketsHref: string
  problems: ProblemVM[]
  programmeHref: string
}

/** Something wrong with the Schedule itself, and the one thing to do. */
export interface ProblemVM {
  id: string
  title: string
  action: "Repair" | "Release"
  /** Already done in the pending Change Set. */
  on: boolean
  onAct: () => void
}

export interface TicketVM {
  id: string
  title: string
  href: string
  when: string
  venue: string
  /** A number or a name; null when the programme does not say. */
  auditorium: string | null
  /** Why it is here and what the ticket allows: "Not scheduled", "Refundable". */
  notes: string[]
  /** Let go only: put it back in the Schedule, through the tray. */
  onKeep?: () => void
  keeping?: boolean
  /** Let go only: the User no longer holds it. */
  onGone?: () => void
  /** Withdrawn only: where to ask for a refund. */
  festivalHref?: string | null
}

export interface TicketsVM {
  letGo: TicketVM[]
  held: TicketVM[]
  programmeHref: string
}

export interface ItemVM {
  verb: ItemVerb
  word: string
  subject: string
  onRemove?: () => void
}

export interface TrayVM {
  items: ItemVM[]
  signedIn: boolean
  busy: boolean
  error: string | null
  onSolve: () => void
  onClear: () => void
}

export interface DiffRowVM {
  id: string
  title: string
  when: string
  venue: string
  /** A number or a name; null when the programme does not say. */
  auditorium: string | null
  ticket: boolean
}

export interface DraftVM {
  status: "solving" | "ready" | "infeasible" | "failed"
  stale: boolean
  scoreDelta: string | null
  /** Screenings the Draft brings into the Schedule. */
  in: DiffRowVM[]
  /** Screenings the Draft takes out of it; not Withdrawn, just not chosen. */
  out: DiffRowVM[]
  droppedTickets: number
  reasons: string[]
  items: ItemVM[]
  busy: boolean
  error: string | null
  onAccept: () => void
  onDiscard: () => void
  onResolve: () => void
}

export interface DraftListItemVM {
  id: string
  href: string
  status: DraftVM["status"]
  stale: boolean
  changes: number
  created: string
}

export interface CompareSideVM {
  title: string
  meta: string[]
  onPick: () => void
}

export interface CompareVM {
  pair: { a: CompareSideVM; b: CompareSideVM } | null
  picked: "a" | "b" | null
  left: number
  onSkip: () => void
}
