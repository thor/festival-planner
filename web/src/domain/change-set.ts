// The pending Change Set: edits collected before a Draft is solved. Pure.
// Toggling works against the accepted inputs, so it never builds a NO_OP or
// COMMITTED_AND_EXCLUDED item that the API would reject.

import type {
  ChangeSetItem,
  PlanningInputs,
  ProgrammeEntryId,
  ScreeningId,
} from "./model"
import { sameValue } from "./equal"
import { defaultPreferences } from "./preferences"

export type ChangeSet = readonly ChangeSetItem[]

export const emptyInputs: PlanningInputs = {
  screeningCommitments: [],
  filmCommitments: [],
  excludedScreenings: [],
  excludedProgrammeEntries: [],
  preferences: defaultPreferences,
}

const same: (a: ChangeSetItem, b: ChangeSetItem) => boolean = sameValue

function without(set: ChangeSet, item: ChangeSetItem): ChangeSet {
  return set.filter((i) => !same(i, item))
}

function has(set: ChangeSet, item: ChangeSetItem): boolean {
  return set.some((i) => same(i, item))
}

export interface ScreeningMarks {
  committed: boolean
  excluded: boolean
  /** Whether the pending Change Set changes this Screening. */
  pending: boolean
}

export function screeningMarks(
  id: ScreeningId,
  inputs: PlanningInputs,
  set: ChangeSet
): ScreeningMarks {
  const s = { screeningId: id }
  const addC = has(set, { kind: "addScreeningCommitment", ...s })
  const relC = has(set, { kind: "releaseScreeningCommitment", ...s })
  const addX = has(set, { kind: "addExcludedScreening", ...s })
  const relX = has(set, { kind: "removeExcludedScreening", ...s })
  const wasC = inputs.screeningCommitments.includes(id)
  const wasX = inputs.excludedScreenings.includes(id)
  return {
    committed: (wasC && !relC) || addC,
    excluded: (wasX && !relX) || addX,
    pending: addC || relC || addX || relX,
  }
}

export interface EntryMarks {
  committed: boolean
  excluded: boolean
  pending: boolean
}

export function entryMarks(
  id: ProgrammeEntryId,
  inputs: PlanningInputs,
  set: ChangeSet
): EntryMarks {
  const e = { programmeEntryId: id }
  const addC = has(set, { kind: "addFilmCommitment", ...e })
  const relC = has(set, { kind: "releaseFilmCommitment", ...e })
  const addX = has(set, { kind: "addExcludedProgrammeEntry", ...e })
  const relX = has(set, { kind: "removeExcludedProgrammeEntry", ...e })
  const wasC = inputs.filmCommitments.includes(id)
  const wasX = inputs.excludedProgrammeEntries.includes(id)
  return {
    committed: (wasC && !relC) || addC,
    excluded: (wasX && !relX) || addX,
    pending: addC || relC || addX || relX,
  }
}

/**
 * Flip one of two opposite settings. `on` is the item that turns it on,
 * `off` the one that turns it off, `was` the accepted state.
 */
function flip(
  set: ChangeSet,
  was: boolean,
  on: ChangeSetItem,
  off: ChangeSetItem
): ChangeSet {
  if (has(set, on)) return without(set, on)
  if (has(set, off)) return without(set, off)
  return [...set, was ? off : on]
}

export function toggleScreeningCommitment(
  id: ScreeningId,
  inputs: PlanningInputs,
  set: ChangeSet
): ChangeSet {
  const s = { screeningId: id }
  const marks = screeningMarks(id, inputs, set)
  let next = flip(
    set,
    inputs.screeningCommitments.includes(id),
    { kind: "addScreeningCommitment", ...s },
    { kind: "releaseScreeningCommitment", ...s }
  )
  if (!marks.committed && marks.excluded)
    next = toggleScreeningExclusion(id, inputs, next)
  return next
}

export function toggleScreeningExclusion(
  id: ScreeningId,
  inputs: PlanningInputs,
  set: ChangeSet
): ChangeSet {
  const s = { screeningId: id }
  const marks = screeningMarks(id, inputs, set)
  let next = flip(
    set,
    inputs.excludedScreenings.includes(id),
    { kind: "addExcludedScreening", ...s },
    { kind: "removeExcludedScreening", ...s }
  )
  if (!marks.excluded && marks.committed)
    next = toggleScreeningCommitment(id, inputs, next)
  return next
}

export function toggleFilmCommitment(
  id: ProgrammeEntryId,
  inputs: PlanningInputs,
  set: ChangeSet
): ChangeSet {
  const e = { programmeEntryId: id }
  const marks = entryMarks(id, inputs, set)
  let next = flip(
    set,
    inputs.filmCommitments.includes(id),
    { kind: "addFilmCommitment", ...e },
    { kind: "releaseFilmCommitment", ...e }
  )
  if (!marks.committed && marks.excluded)
    next = toggleFilmExclusion(id, inputs, next)
  return next
}

export function toggleFilmExclusion(
  id: ProgrammeEntryId,
  inputs: PlanningInputs,
  set: ChangeSet
): ChangeSet {
  const e = { programmeEntryId: id }
  const marks = entryMarks(id, inputs, set)
  let next = flip(
    set,
    inputs.excludedProgrammeEntries.includes(id),
    { kind: "addExcludedProgrammeEntry", ...e },
    { kind: "removeExcludedProgrammeEntry", ...e }
  )
  if (!marks.excluded && marks.committed)
    next = toggleFilmCommitment(id, inputs, next)
  return next
}

/** Replaces any earlier Comparison of the same pair, like the API. */
export function recordComparison(
  preferredId: ProgrammeEntryId,
  otherId: ProgrammeEntryId,
  set: ChangeSet
): ChangeSet {
  const pair = new Set([preferredId, otherId])
  const kept = set.filter(
    (i) =>
      i.kind !== "recordComparison" ||
      !(pair.has(i.preferredId) && pair.has(i.otherId))
  )
  return [...kept, { kind: "recordComparison", preferredId, otherId }]
}

export function removeAt(index: number, set: ChangeSet): ChangeSet {
  return set.filter((_, i) => i !== index)
}

/** The verb an item performs, for an icon and a word. */
export type ItemVerb =
  | "commit"
  | "release"
  | "exclude"
  | "include"
  | "compare"
  | "interest"
  | "buffer"
  | "days"
  | "events"
  | "transport"

export function verbOf(item: ChangeSetItem): ItemVerb {
  switch (item.kind) {
    case "addScreeningCommitment":
    case "addFilmCommitment":
      return "commit"
    case "releaseScreeningCommitment":
    case "releaseFilmCommitment":
      return "release"
    case "addExcludedScreening":
    case "addExcludedProgrammeEntry":
      return "exclude"
    case "removeExcludedScreening":
    case "removeExcludedProgrammeEntry":
      return "include"
    case "recordComparison":
      return "compare"
    case "setProgrammeEntryWeight":
    case "setScreeningWeight":
    case "setYearWeight":
    case "setEventWeight":
    case "setComparisonWeight":
      return "interest"
    case "setBuffer":
      return "buffer"
    case "setDateRange":
      return "days"
    case "setAttendEvents":
      return "events"
    case "setTransportMode":
      return "transport"
  }
}
