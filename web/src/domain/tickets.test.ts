import { describe, expect, it } from "vitest"

import type {
  Flag,
  ProgrammeEntry,
  ProgrammeEntryId,
  Screening,
  ScreeningId,
  Ticket,
} from "./model"
import { festivalTickets, scheduleProblems, sortTickets } from "./tickets"

const now = new Date("2026-10-23T12:00:00Z")

function screening(id: string, start: string, withdrawn = false): Screening {
  return {
    id: id as ScreeningId,
    programmeEntryId: "e" as ProgrammeEntryId,
    title: id,
    startTime: start,
    endTime: start,
    venue: { id: "v" as never, name: "V" },
    auditorium: null,
    ticketUrl: null,
    events: [],
    withdrawn,
  }
}

const ticket = (s: Screening): Ticket => ({
  screening: s,
  exchangeable: false,
  refundable: false,
})
const flag = (kind: Flag["kind"], s: Screening): Flag => ({
  kind,
  message: "",
  screening: s,
  programmeEntryId: null,
})

const scheduled = screening("scheduled", "2026-10-25T18:00:00Z")
const loose = screening("loose", "2026-10-24T18:00:00Z")
const gone = screening("gone", "2026-10-26T18:00:00Z", true)
const past = screening("past", "2026-10-20T18:00:00Z")

describe("sortTickets", () => {
  it("lets go of withdrawn and unscheduled tickets, by start time", () => {
    const sorted = sortTickets(
      [ticket(gone), ticket(scheduled), ticket(loose)],
      new Set([scheduled.id]),
      now
    )
    expect(sorted.letGo.map((l) => [l.ticket.screening.id, l.reason])).toEqual([
      ["loose", "notScheduled"],
      ["gone", "withdrawn"],
    ])
    expect(sorted.held.map((t) => t.screening.id)).toEqual(["scheduled"])
  })

  it("holds a past ticket even if unscheduled: there is nothing left to do", () => {
    expect(sortTickets([ticket(past)], new Set(), now).held).toHaveLength(1)
  })
})

describe("festivalTickets", () => {
  it("keeps tickets in the programme or named by a Flag", () => {
    const entry = { screenings: [loose] } as unknown as ProgrammeEntry
    const other = screening("other-festival", "2026-10-24T18:00:00Z")
    const mine = festivalTickets(
      [ticket(loose), ticket(gone), ticket(other)],
      [entry],
      [flag("WITHDRAWN_TICKET", gone)]
    )
    expect(mine.map((t) => t.screening.id)).toEqual(["loose", "gone"])
  })
})

describe("scheduleProblems", () => {
  it("leaves ticket Flags to the Tickets page", () => {
    const flags = [
      flag("UNSCHEDULED_TICKET", loose),
      flag("WITHDRAWN_IN_SCHEDULE", gone),
      flag("WITHDRAWN_TICKET", gone),
      flag("WITHDRAWN_COMMITMENT", gone),
    ]
    expect(scheduleProblems(flags).map((f) => f.kind)).toEqual([
      "WITHDRAWN_IN_SCHEDULE",
      "WITHDRAWN_COMMITMENT",
    ])
  })
})
