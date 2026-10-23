import { describe, expect, it } from "vitest"

import {
  emptyInputs,
  recordComparison,
  screeningMarks,
  toggleScreeningCommitment,
  toggleScreeningExclusion,
} from "./change-set"
import type {
  Festival,
  FestivalId,
  PlanningInputs,
  ProgrammeEntryId,
  Screening,
  ScreeningId,
} from "./model"
import { clock, dayKey, festivalDays, minuteOfDay } from "./time"
import {
  DEFAULT_SPAN,
  fitSpan,
  hourTicks,
  layDays,
  layDiff,
  nowOn,
} from "./timeline"

const s1 = "s1" as ScreeningId
const a = "a" as ProgrammeEntryId
const b = "b" as ProgrammeEntryId

describe("change set", () => {
  it("adds, then cancels, a Screening Commitment", () => {
    const once = toggleScreeningCommitment(s1, emptyInputs, [])
    expect(once).toEqual([{ kind: "addScreeningCommitment", screeningId: s1 }])
    expect(toggleScreeningCommitment(s1, emptyInputs, once)).toEqual([])
  })

  it("releases an accepted commitment instead of adding a no-op", () => {
    const inputs: PlanningInputs = {
      ...emptyInputs,
      screeningCommitments: [s1],
    }
    expect(toggleScreeningCommitment(s1, inputs, [])).toEqual([
      { kind: "releaseScreeningCommitment", screeningId: s1 },
    ])
  })

  it("never leaves a Screening committed and excluded", () => {
    const committed = toggleScreeningCommitment(s1, emptyInputs, [])
    const excluded = toggleScreeningExclusion(s1, emptyInputs, committed)
    expect(excluded).toEqual([
      { kind: "addExcludedScreening", screeningId: s1 },
    ])
    expect(screeningMarks(s1, emptyInputs, excluded)).toEqual({
      committed: false,
      excluded: true,
      pending: true,
    })
  })

  it("keeps one Comparison per pair, latest wins", () => {
    const set = recordComparison(b, a, recordComparison(a, b, []))
    expect(set).toEqual([
      { kind: "recordComparison", preferredId: b, otherId: a },
    ])
  })
})

const festival: Festival = {
  id: "f" as FestivalId,
  slug: "f",
  name: "F",
  startDate: "2026-10-24",
  endDate: "2026-10-26",
  timeZone: "Europe/Oslo",
}

describe("time", () => {
  it("reads instants in the Festival's zone, across the DST change", () => {
    expect(clock("2026-10-24T16:00:00Z", "Europe/Oslo")).toBe("18:00")
    expect(clock("2026-10-26T16:00:00Z", "Europe/Oslo")).toBe("17:00")
    expect(dayKey("2026-10-24T22:30:00Z", "Europe/Oslo")).toBe("2026-10-25")
  })

  it("counts after-midnight minutes past 24h on the screening's day", () => {
    expect(
      minuteOfDay("2026-10-24T22:30:00Z", "2026-10-24", "Europe/Oslo")
    ).toBe(24 * 60 + 30)
  })

  it("lists every Festival day", () => {
    expect(festivalDays(festival)).toEqual([
      "2026-10-24",
      "2026-10-25",
      "2026-10-26",
    ])
  })
})

const screening = (
  startTime: string,
  endTime: string,
  id = "s1"
): Screening => ({
  id: id as ScreeningId,
  programmeEntryId: a,
  title: id,
  startTime,
  endTime,
  venue: { id: "v" as never, name: "V" },
  auditorium: null,
  ticketUrl: null,
  events: [],
  withdrawn: false,
})

describe("timeline", () => {
  // Oslo is UTC+2 on 24 October.
  it("fits the span to every Screening, with half an hour either side", () => {
    // 17:30 to 19:00, and 21:15 to 00:40.
    const span = fitSpan(festival, [
      screening("2026-10-24T15:30:00Z", "2026-10-24T17:00:00Z"),
      screening("2026-10-24T19:15:00Z", "2026-10-24T22:40:00Z"),
    ])
    expect(span).toEqual({ start: 17 * 60, end: 24 * 60 + 40 + 30 })
  })

  it("ticks on whole hours, every other hour on a long span", () => {
    const labels = (start: number, end: number) =>
      hourTicks({ start, end }).map((t) => t.label)
    expect(labels(21 * 60 + 30, 24 * 60 + 30)).toEqual(["22", "23", "00"])
    expect(labels(10 * 60, 25 * 60).slice(0, 2)).toEqual(["10", "12"])
  })

  it("puts now on its day, and just after midnight on the evening before", () => {
    const on = (now: string) => nowOn(festival, DEFAULT_SPAN, now)?.day
    expect(on("2026-10-24T16:00:00Z")).toBe("2026-10-24") // 18:00
    expect(on("2026-10-24T22:30:00Z")).toBe("2026-10-24") // 00:30
    expect(on("2026-10-24T06:00:00Z")).toBeUndefined() // 08:00, off the span
  })

  it("places a Screening by time on its day", () => {
    const rows = layDays(
      festival,
      [screening("2026-10-24T15:30:00Z", "2026-10-24T17:00:00Z")],
      DEFAULT_SPAN
    )
    expect(rows.map((r) => r.placed.length)).toEqual([1, 0, 0])
    const { left, width } = rows[0].placed[0]
    expect(left).toBeCloseTo((17.5 - 10) / 15)
    expect(width).toBeCloseTo(1.5 / 15)
  })
})

describe("draft timeline", () => {
  const at = (id: string, day: string) =>
    screening(`${day}T15:30:00Z`, `${day}T17:00:00Z`, id)

  it("tags each Screening In, Out or kept, on one set of days", () => {
    const kept = at("kept", "2026-10-24")
    const added = at("in", "2026-10-25")
    const out = at("out", "2026-10-25")
    const rows = layDiff(
      festival,
      [kept, added],
      { added: [added], removed: [out] },
      DEFAULT_SPAN
    )
    expect(rows.map((r) => r.day)).toEqual([
      "2026-10-24",
      "2026-10-25",
      "2026-10-26",
    ])
    expect(rows.map((r) => r.changed)).toEqual([false, true, false])
    expect(rows[1].placed.map((p) => [p.screening.id, p.change])).toEqual([
      ["in", "in"],
      ["out", "out"],
    ])
    expect(rows[0].placed[0].change).toBe("kept")
  })
})
