// Preferences and the Change Set items that set them. Pure. The setting key
// and the rule for applying an item mirror the backend's (change_sets.py), so
// the pending Change Set never holds a NO_OP or two items for one setting.

import type { ChangeSet } from "./change-set"
import type {
  ChangeSetItem,
  DayKey,
  Festival,
  PreferenceItem,
  Preferences,
} from "./model"

export const defaultPreferences: Preferences = {
  bufferMinutes: 15,
  venueBuffers: {},
  startDate: null,
  endDate: null,
  entryWeights: {},
  screeningWeights: {},
  yearWeights: {},
  eventWeight: 0,
  attendEvents: false,
  transportMode: null,
  comparisonWeight: 0.5,
  comparisons: [],
}

const preferenceKinds = new Set<ChangeSetItem["kind"]>([
  "setProgrammeEntryWeight",
  "setScreeningWeight",
  "setYearWeight",
  "setBuffer",
  "setDateRange",
  "setEventWeight",
  "setAttendEvents",
  "setTransportMode",
  "setComparisonWeight",
])

export function isPreference(item: ChangeSetItem): item is PreferenceItem {
  return preferenceKinds.has(item.kind)
}

/** What an item sets. Two items of one Change Set must not share it. */
export function settingOf(item: PreferenceItem): string {
  switch (item.kind) {
    case "setProgrammeEntryWeight":
      return `entryWeight:${item.programmeEntryId}`
    case "setScreeningWeight":
      return `screeningWeight:${item.screeningId}`
    case "setYearWeight":
      return `yearWeight:${item.year}`
    case "setBuffer":
      return `buffer:${item.venueId ?? ""}`
    default:
      return item.kind
  }
}

/** `map` with `key` set to `value`, or without it when `value` is null. */
function put<K extends string | number>(
  map: Readonly<Record<K, number>>,
  key: K,
  value: number | null
): Record<K, number> {
  const next: Record<K, number> = { ...map }
  if (value === null) delete next[key]
  else next[key] = value
  return next
}

/** `p` with one item applied. A null value resets the setting. */
export function applyPreference(
  p: Preferences,
  item: PreferenceItem
): Preferences {
  const d = defaultPreferences
  switch (item.kind) {
    case "setProgrammeEntryWeight":
      return {
        ...p,
        entryWeights: put(p.entryWeights, item.programmeEntryId, item.weight),
      }
    case "setScreeningWeight":
      return {
        ...p,
        screeningWeights: put(
          p.screeningWeights,
          item.screeningId,
          item.weight
        ),
      }
    case "setYearWeight":
      return { ...p, yearWeights: put(p.yearWeights, item.year, item.weight) }
    case "setBuffer":
      return item.venueId === null
        ? { ...p, bufferMinutes: item.minutes ?? d.bufferMinutes }
        : {
            ...p,
            venueBuffers: put(p.venueBuffers, item.venueId, item.minutes),
          }
    case "setDateRange":
      return { ...p, startDate: item.startDate, endDate: item.endDate }
    case "setEventWeight":
      return { ...p, eventWeight: item.weight ?? d.eventWeight }
    case "setAttendEvents":
      return { ...p, attendEvents: item.attend ?? d.attendEvents }
    case "setTransportMode":
      return { ...p, transportMode: item.mode }
    case "setComparisonWeight":
      return { ...p, comparisonWeight: item.weight ?? d.comparisonWeight }
  }
}

/** `p` as it would be once `set` is accepted. */
export function preferencesAfter(p: Preferences, set: ChangeSet): Preferences {
  let next = p
  for (const item of set) {
    if (isPreference(item)) next = applyPreference(next, item)
    else if (item.kind === "recordComparison") {
      const pair = [item.preferredId, item.otherId]
      next = {
        ...next,
        comparisons: [
          ...next.comparisons.filter(
            (c) => !(pair.includes(c.preferredId) && pair.includes(c.otherId))
          ),
          { preferredId: item.preferredId, otherId: item.otherId },
        ],
      }
    }
  }
  return next
}

/** JSON with sorted keys, so equal values give equal text. */
function canonical(value: unknown): string {
  return JSON.stringify(value, (_, v: unknown) =>
    v && typeof v === "object" && !Array.isArray(v)
      ? Object.fromEntries(
          Object.entries(v).sort(([a], [b]) => a.localeCompare(b))
        )
      : v
  )
}

/**
 * Put `item` in the pending Change Set, replacing any earlier item for the
 * same setting. If it would leave the accepted Preferences as they are, the
 * setting is simply no longer pending.
 */
export function setPreference(
  item: PreferenceItem,
  accepted: Preferences,
  set: ChangeSet
): ChangeSet {
  const key = settingOf(item)
  const at = set.findIndex((i) => isPreference(i) && settingOf(i) === key)
  const rest = set.filter((_, i) => i !== at)
  if (canonical(applyPreference(accepted, item)) === canonical(accepted))
    return rest
  if (at < 0) return [...set, item]
  return set.map((i, n) => (n === at ? item : i))
}

/**
 * The days from `a` to `b`, either way round. Every Festival Day is no range
 * at all, so it matches the default.
 */
export function dateRangeItem(
  a: DayKey,
  b: DayKey,
  festival: Pick<Festival, "startDate" | "endDate">
): PreferenceItem {
  const [start, end] = a <= b ? [a, b] : [b, a]
  const whole = start <= festival.startDate && end >= festival.endDate
  return {
    kind: "setDateRange",
    startDate: whole ? null : start,
    endDate: whole ? null : end,
  }
}

/** Whether `day` is inside the preferred days. */
export function inRange(day: DayKey, p: Preferences): boolean {
  return (
    (!p.startDate || day >= p.startDate) && (!p.endDate || day <= p.endDate)
  )
}

/** Whether the pending Change Set changes this setting. */
export function isPending(set: ChangeSet, item: PreferenceItem): boolean {
  const key = settingOf(item)
  return set.some((i) => isPreference(i) && settingOf(i) === key)
}

// --- Interest: a weight in four steps ---------------------------------------

export type Interest = "less" | "usual" | "more" | "most"

export const interests: readonly Interest[] = ["less", "usual", "more", "most"]

/** The value for each step; `usual` is the setting's default. */
export type Scale = Readonly<Record<Interest, number>>

/** A Programme Entry's weight. */
export const entryScale: Scale = { less: 0.5, usual: 1, more: 1.5, most: 2 }

/**
 * Added on top of an entry's weight, so kept small: Less on both still
 * leaves a film worth seeing.
 */
export const offsetScale: Scale = {
  less: -0.25,
  usual: 0,
  more: 0.25,
  most: 0.5,
}

/** How strongly Comparisons count. Never negative. */
export const comparisonScale: Scale = {
  less: 0.25,
  usual: 0.5,
  more: 1,
  most: 1.5,
}

/** The step nearest to `value`. */
export function interestOf(value: number | undefined, scale: Scale): Interest {
  if (value === undefined) return "usual"
  let best: Interest = "usual"
  for (const i of interests)
    if (Math.abs(scale[i] - value) < Math.abs(scale[best] - value)) best = i
  return best
}

/** The value to send for a step: null for usual, which resets it. */
export function valueOf(interest: Interest, scale: Scale): number | null {
  return interest === "usual" ? null : scale[interest]
}
