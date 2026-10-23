// Preferences as view models: the Interest control, and the Preferences
// page. Edits go into the pending Change Set like any other change.

import { useState } from "react"

import { daysWord, interestWord, plural } from "@/domain/labels"
import type {
  DayKey,
  Festival,
  Planning,
  PreferenceItem,
  ProgrammeEntry,
  VenueId,
} from "@/domain/model"
import {
  bufferItem,
  comparisonScale,
  daysItem,
  defaultPreferences,
  entryScale,
  interestOf,
  interests,
  isPending,
  offsetScale,
  paintDays,
  preferencesAfter,
  runsOf,
  setPreference,
  valueOf,
  type Interest,
  type Scale,
} from "@/domain/preferences"
import { dayNumber, festivalDays, weekday } from "@/domain/time"

import { usePendingChangeSet } from "./change-set-store"
import { useFestival, usePlanning, useProgramme } from "./queries"
import type {
  DaysVM,
  InterestVM,
  Load,
  PreferencesVM,
  StepperVM,
} from "./view-models"

const STEP = 5
const MOST_MINUTES = 90

/** Accepted and pending Preferences for one Festival, and a way to set one. */
export function usePreferences(
  festival: Festival | null | undefined,
  planning: Planning | null | undefined
) {
  const [set, update] = usePendingChangeSet(festival?.id)
  const accepted = planning?.inputs.preferences ?? defaultPreferences
  return {
    /** As they will be once the pending Change Set is accepted. */
    effective: preferencesAfter(accepted, set),
    pending: (item: PreferenceItem) => isPending(set, item),
    /** Missing when signed out. */
    put: planning
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

/** A sweep across the Days strip: where it began, and what it paints. */
interface Sweep {
  origin: DayKey
  on: boolean
  /** The days as they were when the press began. */
  base: readonly DayKey[] | null
  at: DayKey
}

/**
 * The Days strip. A press paints from its day, and a sweep stretches that
 * paint like a rubber band over the days as they were when it began.
 */
function useDays(festival: Festival | null | undefined, prefs: Prefs) {
  const [sweep, setSweep] = useState<Sweep | null>(null)
  // The day touched last and what it got, for Shift to paint from.
  const [last, setLast] = useState<{ day: DayKey; on: boolean } | null>(null)

  return (put: (item: PreferenceItem) => void): DaysVM => {
    const all = festival ? festivalDays(festival) : []
    const days = prefs.effective.days
    const chosen = new Set(days ?? [])
    const paint = (s: Sweep) => {
      put(paintDays(s.base, s.origin, s.at, s.on, all))
      setLast({ day: s.at, on: s.on })
    }
    const every = days === null
    return {
      cells: all.map((d, i) => ({
        key: d,
        number: dayNumber(d),
        weekday: weekday(d),
        chosen: chosen.has(d),
        joinsNext: chosen.has(d) && chosen.has(all[i + 1]),
      })),
      every,
      summary: daysWord(runsOf(days ?? [])),
      count: every
        ? null
        : `${chosen.size} of ${plural(all.length, "day", "days")}`,
      pending: prefs.pending(daysItem([], all)),
      hint: every
        ? "Tap the days you can go, or sweep across several."
        : "Tap or sweep to add days, or to take them away.",
      onPress: (day, extend) => {
        const from = extend && last ? last : null
        const s: Sweep = {
          origin: from?.day ?? day,
          on: from?.on ?? !chosen.has(day),
          base: days,
          at: day,
        }
        setSweep(s)
        paint(s)
      },
      onSweep: (day) => {
        if (!sweep || sweep.at === day) return
        const s = { ...sweep, at: day }
        setSweep(s)
        paint(s)
      },
      onRelease: () => setSweep(null),
      onEveryDay: () => {
        setSweep(null)
        setLast(null)
        put(daysItem([], all))
      },
    }
  }
}

export function usePreferencesPage(slug: string): Load<PreferencesVM> {
  const festival = useFestival(slug)
  const programme = useProgramme(festival.data)
  const planning = usePlanning(festival.data)
  const prefs = usePreferences(festival.data, planning.data)
  const daysOf = useDays(festival.data, prefs)

  if (festival.isPending || programme.isPending || planning.isPending)
    return { state: "loading" }
  if (!festival.data) return { state: "missing", message: "No such festival." }
  const put = prefs.put
  if (!put) return { state: "missing", message: "Sign in to set preferences." }
  const f = festival.data
  const p = prefs.effective
  const entries = programme.data ?? []

  const buffer = (
    label: string,
    venueId: VenueId | null,
    own: number | undefined
  ): StepperVM => {
    const minutes = own ?? p.bufferMinutes
    const reset: PreferenceItem = { kind: "setBuffer", venueId, minutes: null }
    const to = (m: number) => put(bufferItem(venueId, m, p))
    return {
      label,
      minutes,
      usual: venueId
        ? own === undefined
        : minutes === defaultPreferences.bufferMinutes,
      pending: prefs.pending(reset),
      onLess: minutes > 0 ? () => to(minutes - STEP) : undefined,
      onMore: minutes < MOST_MINUTES ? () => to(minutes + STEP) : undefined,
      onReset: venueId && own !== undefined ? () => put(reset) : undefined,
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
      days: daysOf(put),
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
        onToggle: () =>
          put({
            kind: "setAttendEvents",
            attend: p.attendEvents ? null : true,
          }),
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
