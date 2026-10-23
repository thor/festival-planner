import { describe, expect, it } from "vitest"

import { dateSpan, festivalsInOrder, phaseOf } from "./festivals"
import type { Festival, FestivalId } from "./model"

const make = (slug: string, startDate: string, endDate: string): Festival => ({
  id: slug as FestivalId,
  slug,
  name: slug,
  startDate,
  endDate,
  timeZone: "Europe/Oslo",
})

// 12:00 in Oslo on 2026-11-02.
const now = new Date("2026-11-02T11:00:00Z")

describe("festivals", () => {
  it("knows a Festival on now, ahead and over, by its own time zone", () => {
    expect(phaseOf(make("on", "2026-10-30", "2026-11-08"), now)).toBe("now")
    expect(phaseOf(make("ahead", "2026-11-03", "2026-11-08"), now)).toBe(
      "ahead"
    )
    expect(phaseOf(make("over", "2026-10-20", "2026-11-01"), now)).toBe("over")
    // 23:30 UTC on the 1st is already the 2nd in Oslo.
    expect(
      phaseOf(
        make("starts", "2026-11-02", "2026-11-04"),
        new Date("2026-11-01T23:30:00Z")
      )
    ).toBe("now")
  })

  it("puts what is on first, then the soonest, then the most recent past", () => {
    const order = festivalsInOrder(
      [
        make("old", "2025-11-06", "2025-11-16"),
        make("later", "2027-06-01", "2027-06-07"),
        make("on", "2026-10-30", "2026-11-08"),
        make("soon", "2026-11-20", "2026-11-25"),
        make("recent", "2026-09-20", "2026-09-27"),
      ],
      now
    ).map((f) => f.slug)
    expect(order).toEqual(["on", "soon", "later", "recent", "old"])
  })

  it("writes a date span as briefly as it reads", () => {
    expect(dateSpan(make("a", "2026-11-06", "2026-11-16"))).toBe(
      "6–16 November 2026"
    )
    expect(dateSpan(make("b", "2026-10-30", "2026-11-08"))).toBe(
      "30 October – 8 November 2026"
    )
    expect(dateSpan(make("c", "2026-12-28", "2027-01-03"))).toBe(
      "28 December 2026 – 3 January 2027"
    )
    expect(dateSpan(make("d", "2026-06-01", "2026-06-01"))).toBe("1 June 2026")
  })
})
