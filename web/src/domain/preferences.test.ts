import { describe, expect, it } from "vitest"

import type {
  PreferenceItem,
  Preferences,
  ProgrammeEntryId,
  VenueId,
} from "./model"
import {
  bufferItem,
  defaultPreferences,
  entryScale,
  interestOf,
  isPending,
  offsetScale,
  preferencesAfter,
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

  it("treats the date range as one setting", () => {
    const range = (startDate: string | null, endDate: string | null) =>
      ({ kind: "setDateRange", startDate, endDate }) as const
    const set = setPreference(
      range("2026-10-30", "2026-11-02"),
      defaultPreferences,
      [range("2026-10-30", null)]
    )
    expect(set).toEqual([range("2026-10-30", "2026-11-02")])
    expect(setPreference(range(null, null), defaultPreferences, set)).toEqual(
      []
    )
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
