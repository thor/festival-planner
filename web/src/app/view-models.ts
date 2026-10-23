// What views render. Plain data and callbacks; no domain types leak through.

import type { ItemVerb } from "@/domain/change-set"

export type Load<T> =
  | { state: "loading" }
  | { state: "missing"; message: string }
  | { state: "ready"; value: T }

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
  venue: string
  href: string
  left: number
  width: number
  ticket: boolean
  committed: boolean
  withdrawn: boolean
}

export interface WeekDayVM {
  key: string
  number: string
  weekday: string
  blocks: BlockVM[]
}

export interface WeekVM {
  number: number | null
  count: number
  days: WeekDayVM[]
  ticks: { label: string; left: number }[]
  flags: string[]
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
  ticket: boolean
}

export interface DraftVM {
  status: "solving" | "ready" | "infeasible" | "failed"
  stale: boolean
  scoreDelta: string | null
  added: DiffRowVM[]
  removed: DiffRowVM[]
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
