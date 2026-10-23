import { describe, expect, it } from "vitest"

import type {
  PreferenceItem,
  Preferences,
  ProgrammeEntryId,
  VenueId,
} from "./model"
import {
  bufferItem,
  daysItem,
  defaultPreferences,
  entryScale,
  interestOf,
  isPending,
  offsetScale,
  paintDays,
  preferencesAfter,
  runsOf,
  setPreference,
  valueOf,
} from "./preferences"

const a = "a" as ProgrammeEntryId
const vika = "vika" as VenueId
const weigh = (weight: number | null): PreferenceItem => ({
  kind: "setProgrammeEntryWeight",
  programmeEntryId: a,
  weight,
})

describe("setPreference", () => {
  it("adds a setting that changes something", () => {
    expect(setPreference(weigh(2), defaultPreferences, [])).toEqual([weigh(2)])
  })

  it("replaces an earlier item for the same setting, in place", () => {
    const set = [weigh(2), { kind: "setEventWeight", weight: 0.5 } as const]
    expect(setPreference(weigh(1.5), defaultPreferences, set)).toEqual([
      weigh(1.5),
      set[1],
    ])
  })

  it("drops the item when it would change nothing", () => {
    expect(setPreference(weigh(null), defaultPreferences, [weigh(2)])).toEqual(
      []
    )
  })

  it("resets a stored weight with null, not the default value", () => {
    const stored: Preferences = {
      ...defaultPreferences,
      entryWeights: { [a]: 2 },
    }
    expect(setPreference(weigh(null), stored, [])).toEqual([weigh(null)])
  })

  it("keeps the general buffer and a Venue's apart", () => {
    const general = { kind: "setBuffer", venueId: null, minutes: 20 } as const
    const atVika = { kind: "setBuffer", venueId: vika, minutes: 30 } as const
    const set = setPreference(
      atVika,
      defaultPreferences,
      setPreference(general, defaultPreferences, [])
    )
    expect(set).toEqual([general, atVika])
    expect(preferencesAfter(defaultPreferences, set)).toMatchObject({
      bufferMinutes: 20,
      venueBuffers: { [vika]: 30 },
    })
  })

  it("treats the days as one setting", () => {
    const days = (...d: string[]) => ({ kind: "setDays", days: d }) as const
    const set = setPreference(days(D1, D3), defaultPreferences, [days(D1)])
    expect(set).toEqual([days(D1, D3)])
    expect(
      setPreference({ kind: "setDays", days: null }, defaultPreferences, set)
    ).toEqual([])
  })

  it("says which settings are pending", () => {
    expect(isPending([weigh(2)], weigh(null))).toBe(true)
    expect(isPending([weigh(2)], { kind: "setEventWeight", weight: 1 })).toBe(
      false
    )
  })
})

describe("interest", () => {
  it("reads a weight as its nearest step", () => {
    expect(interestOf(undefined, entryScale)).toBe("usual")
    expect(interestOf(2, entryScale)).toBe("most")
    expect(interestOf(1.4, entryScale)).toBe("more")
    expect(interestOf(-0.25, offsetScale)).toBe("less")
  })

  it("sends null for usual, so it resets", () => {
    expect(valueOf("usual", entryScale)).toBeNull()
    expect(valueOf("more", entryScale)).toBe(1.5)
  })
})

const FEST = ["2026-10-30", "2026-10-31", "2026-11-01", "2026-11-02"]
const [D1, D2, D3, D4] = FEST

describe("days", () => {
  it("starts a choice from every day with only the days painted", () => {
    expect(paintDays(null, D2, D3, true, FEST).days).toEqual([D2, D3])
  })

  it("takes days away, and every day off is every day again", () => {
    expect(paintDays([D1, D2, D4], D2, D2, false, FEST).days).toEqual([D1, D4])
    expect(paintDays([D2], D2, D2, false, FEST).days).toBeNull()
  })

  it("paints a sweep either way round", () => {
    expect(paintDays([D1], D4, D3, true, FEST).days).toEqual([D1, D3, D4])
  })

  it("takes away from every day when a sweep turns days off", () => {
    expect(paintDays(null, D1, D2, false, FEST).days).toEqual([D3, D4])
  })

  it("calls every day chosen no choice at all", () => {
    expect(daysItem(FEST, FEST).days).toBeNull()
    expect(daysItem([D4, D1, D1], FEST).days).toEqual([D1, D4])
  })

  it("finds unbroken runs", () => {
    expect(runsOf([D4, D1, D2])).toEqual([
      { first: D1, last: D2 },
      { first: D4, last: D4 },
    ])
  })
})

describe("bufferItem", () => {
  it("lets a Venue set to the general buffer follow it again", () => {
    expect(bufferItem(vika, 15, defaultPreferences)).toEqual({
      kind: "setBuffer",
      venueId: vika,
      minutes: null,
    })
    expect(bufferItem(vika, 20, defaultPreferences).minutes).toBe(20)
    expect(bufferItem(null, 15, defaultPreferences).minutes).toBe(15)
  })
})
