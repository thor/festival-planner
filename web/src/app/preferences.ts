// Preferences as view models: the Interest control, and the Preferences
// page. Edits go into the pending Change Set like any other change.

import { useState } from "react"

import { dayRange, interestWord } from "@/domain/labels"
import type {
  DayKey,
  Festival,
  Planning,
  PreferenceItem,
  ProgrammeEntry,
  VenueId,
} from "@/domain/model"
import {
  comparisonScale,
  dateRangeItem,
  defaultPreferences,
  entryScale,
  inRange,
  interestOf,
  interests,
  isPending,
  offsetScale,
  preferencesAfter,
  setPreference,
  valueOf,
  type Interest,
  type Scale,
} from "@/domain/preferences"
import { dayNumber, festivalDays, weekday } from "@/domain/time"

import { usePendingChangeSet } from "./change-set-store"
import { useFestival, usePlanning, useProgramme } from "./queries"
import type { InterestVM, Load, PreferencesVM, StepperVM } from "./view-models"

const STEP = 5
const MOST_MINUTES = 90

/** Accepted and pending Preferences for one Festival, and a way to set one. */
export function usePreferences(
  festival: Festival | null | undefined,
  planning: Planning | null | undefined
) {
  const [set, update] = usePendingChangeSet(festival?.id)
  const accepted = planning?.inputs.preferences ?? defaultPreferences
  const signedIn = !!planning
  return {
    signedIn,
    /** As they will be once the pending Change Set is accepted. */
    effective: preferencesAfter(accepted, set),
    pending: (item: PreferenceItem) => isPending(set, item),
    put: signedIn
      ? (item: PreferenceItem) =>
          update((cs) => setPreference(item, accepted, cs))
      : undefined,
  }
}

type Prefs = ReturnType<typeof usePreferences>

/** A four-step control over a weight, sending null for usual. */
export function interestModel(
  label: string,
  value: number | undefined,
  scale: Scale,
  item: (weight: number | null) => PreferenceItem,
  prefs: Prefs
): InterestVM {
  const put = prefs.put
  return {
    label,
    options: interests.map((i) => ({ value: i, word: interestWord[i] })),
    value: interestOf(value, scale),
    pending: prefs.pending(item(null)),
    onPick: put && ((i) => put(item(valueOf(i as Interest, scale)))),
  }
}

export function entryInterest(entry: ProgrammeEntry, prefs: Prefs) {
  return interestModel(
    `Interest in ${entry.title}`,
    prefs.effective.entryWeights[entry.id],
    entryScale,
    (weight) => ({
      kind: "setProgrammeEntryWeight",
      programmeEntryId: entry.id,
      weight,
    }),
    prefs
  )
}

/** "More" for a Programme row; null when usual. */
export function entryInterestWord(entry: ProgrammeEntry, prefs: Prefs) {
  const i = interestOf(prefs.effective.entryWeights[entry.id], entryScale)
  return i === "usual" ? null : interestWord[i]
}

const plural = (n: number, one: string, many: string) =>
  `${n} ${n === 1 ? one : many}`

export function usePreferencesPage(slug: string): Load<PreferencesVM> {
  const festival = useFestival(slug)
  const programme = useProgramme(festival.data)
  const planning = usePlanning(festival.data)
  const prefs = usePreferences(festival.data, planning.data)
  // The first day tapped, waiting for the last.
  const [anchor, setAnchor] = useState<DayKey | null>(null)

  if (festival.isPending || programme.isPending || planning.isPending)
    return { state: "loading" }
  if (!festival.data) return { state: "missing", message: "No such festival." }
  if (!planning.data)
    return { state: "missing", message: "Sign in to set preferences." }
  const f = festival.data
  const p = prefs.effective
  const put = prefs.put
  const entries = programme.data ?? []

  const range = dateRangeItem(f.startDate, f.endDate, f)
  const pickDay = (day: DayKey) => {
    if (!put) return
    if (anchor === null) {
      setAnchor(day)
      put(dateRangeItem(day, day, f))
    } else {
      setAnchor(null)
      put(dateRangeItem(anchor, day, f))
    }
  }

  const buffer = (
    label: string,
    venueId: VenueId | null,
    own: number | undefined
  ): StepperVM => {
    const minutes = own ?? p.bufferMinutes
    const item = (m: number | null): PreferenceItem => ({
      kind: "setBuffer",
      venueId,
      minutes: m,
    })
    // A Venue set back to the general buffer follows it again.
    const to = (m: number) =>
      put?.(item(venueId && m === p.bufferMinutes ? null : m))
    return {
      label,
      minutes,
      usual: venueId
        ? own === undefined
        : minutes === defaultPreferences.bufferMinutes,
      pending: prefs.pending(item(null)),
      onLess: put && minutes > 0 ? () => to(minutes - STEP) : undefined,
      onMore:
        put && minutes < MOST_MINUTES ? () => to(minutes + STEP) : undefined,
      onReset:
        put && venueId && own !== undefined ? () => put(item(null)) : undefined,
    }
  }

  const venues = [
    ...new Map(
      entries
        .flatMap((e) => e.screenings)
        .map((s) => [s.venue.id, s.venue] as const)
    ).values(),
  ].sort((a, b) => a.name.localeCompare(b.name))

  const years = [
    ...entries.reduce((count, e) => {
      if (e.year !== null) count.set(e.year, (count.get(e.year) ?? 0) + 1)
      return count
    }, new Map<number, number>()),
  ].sort(([a], [b]) => b - a)

  return {
    state: "ready",
    value: {
      days: festivalDays(f).map((d) => ({
        key: d,
        number: dayNumber(d),
        weekday: weekday(d),
        inRange: inRange(d, p),
        anchor: d === anchor,
        onPick: put && (() => pickDay(d)),
      })),
      range: dayRange(p.startDate, p.endDate),
      rangePending: prefs.pending(range),
      rangeHint: anchor
        ? "Now tap the last day."
        : "Tap the first day, then the last.",
      onEveryDay:
        put && (p.startDate || p.endDate)
          ? () => {
              setAnchor(null)
              put(range)
            }
          : undefined,
      buffer: buffer("Everywhere", null, p.bufferMinutes),
      venues: venues.map((v) => buffer(v.name, v.id, p.venueBuffers[v.id])),
      events: interestModel(
        "Screenings with events",
        p.eventWeight,
        offsetScale,
        (weight) => ({ kind: "setEventWeight", weight }),
        prefs
      ),
      attendEvents: {
        on: p.attendEvents,
        pending: prefs.pending({ kind: "setAttendEvents", attend: null }),
        onToggle:
          put &&
          (() =>
            put({
              kind: "setAttendEvents",
              attend: p.attendEvents ? null : true,
            })),
      },
      years: years.map(([year, films]) => ({
        year: String(year),
        films: plural(films, "film", "films"),
        interest: interestModel(
          `Interest in films from ${year}`,
          p.yearWeights[year],
          offsetScale,
          (weight) => ({ kind: "setYearWeight", year, weight }),
          prefs
        ),
      })),
      comparisons: {
        made: plural(p.comparisons.length, "comparison", "comparisons"),
        href: `/${f.slug}/compare`,
        interest: interestModel(
          "How much comparisons count",
          p.comparisonWeight,
          comparisonScale,
          (weight) => ({ kind: "setComparisonWeight", weight }),
          prefs
        ),
      },
    },
  }
}
