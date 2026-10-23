// An in-memory PlanningPort. Its solver is greedy, not optimal: good enough
// to show Drafts, diffs and Comparisons without a server.

import type { ChangeSet } from "@/domain/change-set"
import { PortError } from "@/domain/errors"
import type {
  ComparisonPair,
  Draft,
  DraftDiff,
  DraftId,
  Flag,
  PlanningInputs,
  Preferences,
  ProgrammeEntryId,
  Schedule,
  ScheduleId,
  Screening,
  ScreeningId,
  Ticket,
} from "@/domain/model"
import { defaultPreferences, preferencesAfter } from "@/domain/preferences"
import type { PlanningPort, SessionPort } from "@/domain/ports"
import { dayKey } from "@/domain/time"

import { festival, programme } from "./seed"

const SOLVE_MS = 900

const all = programme.flatMap((e) => e.screenings)
const byId = new Map(all.map((s) => [s.id, s]))
const screening = (id: ScreeningId) => byId.get(id)!
const noBuffer: Preferences = { ...defaultPreferences, bufferMinutes: 0 }

interface State {
  inputs: PlanningInputs
  schedules: Schedule[]
  drafts: Draft[]
  tickets: Ticket[]
  nextId: number
}

/** The accepted inputs with `set` applied, as the backend would. */
function apply(inputs: PlanningInputs, set: ChangeSet): PlanningInputs {
  const next: PlanningInputs = {
    ...inputs,
    preferences: preferencesAfter(inputs.preferences, set),
  }
  const add = <T>(list: T[], v: T) => (list.includes(v) ? list : [...list, v])
  const drop = <T>(list: T[], v: T) => list.filter((x) => x !== v)
  for (const item of set) {
    switch (item.kind) {
      case "addScreeningCommitment":
        next.screeningCommitments = add(
          next.screeningCommitments,
          item.screeningId
        )
        break
      case "releaseScreeningCommitment":
        next.screeningCommitments = drop(
          next.screeningCommitments,
          item.screeningId
        )
        break
      case "addFilmCommitment":
        next.filmCommitments = add(next.filmCommitments, item.programmeEntryId)
        break
      case "releaseFilmCommitment":
        next.filmCommitments = drop(next.filmCommitments, item.programmeEntryId)
        break
      case "addExcludedScreening":
        next.excludedScreenings = add(next.excludedScreenings, item.screeningId)
        break
      case "removeExcludedScreening":
        next.excludedScreenings = drop(
          next.excludedScreenings,
          item.screeningId
        )
        break
      case "addExcludedProgrammeEntry":
        next.excludedProgrammeEntries = add(
          next.excludedProgrammeEntries,
          item.programmeEntryId
        )
        break
      case "removeExcludedProgrammeEntry":
        next.excludedProgrammeEntries = drop(
          next.excludedProgrammeEntries,
          item.programmeEntryId
        )
        break
    }
  }
  return next
}

/** A rough stand-in for the backend's weights: no Bradley–Terry fit. */
function weightOf(s: Screening, p: Preferences): number {
  const entry = programme.find((e) => e.id === s.programmeEntryId)
  let w = p.screeningWeights[s.id] ?? p.entryWeights[s.programmeEntryId] ?? 1
  if (entry?.year != null) w += p.yearWeights[entry.year] ?? 0
  if (s.events.length) w += p.eventWeight
  for (const c of p.comparisons) {
    if (c.preferredId === s.programmeEntryId) w += p.comparisonWeight / 2
    if (c.otherId === s.programmeEntryId) w -= p.comparisonWeight / 2
  }
  return w
}

function fits(chosen: Screening[], s: Screening, p: Preferences): boolean {
  const gap = (x: Screening) =>
    (p.venueBuffers[x.venue.id] ?? p.bufferMinutes) * 60000
  return chosen.every(
    (c) =>
      Date.parse(c.endTime) + gap(s) <= Date.parse(s.startTime) ||
      Date.parse(s.endTime) + gap(c) <= Date.parse(c.startTime)
  )
}

function solve(inputs: PlanningInputs) {
  const p = inputs.preferences
  const chosen: Screening[] = inputs.screeningCommitments.map(screening)
  const done = new Set(chosen.map((s) => s.programmeEntryId))
  const inRange = (s: Screening) => {
    const day = dayKey(s.startTime, festival.timeZone)
    return (
      (!p.startDate || day >= p.startDate) && (!p.endDate || day <= p.endDate)
    )
  }
  const open = (s: Screening) =>
    !s.withdrawn &&
    inRange(s) &&
    !inputs.excludedScreenings.includes(s.id) &&
    fits(chosen, s, p)

  for (const entryId of inputs.filmCommitments) {
    if (done.has(entryId)) continue
    const pick = programme.find((e) => e.id === entryId)?.screenings.find(open)
    if (!pick) return { status: "INFEASIBLE" as const, chosen: [], score: 0 }
    chosen.push(pick)
    done.add(entryId)
  }
  const rest = all
    .filter(
      (s) =>
        !done.has(s.programmeEntryId) &&
        !inputs.excludedProgrammeEntries.includes(s.programmeEntryId) &&
        weightOf(s, p) > 0
    )
    .sort((a, b) => weightOf(b, p) - weightOf(a, p))
  for (const s of rest) {
    if (done.has(s.programmeEntryId) || !open(s)) continue
    chosen.push(s)
    done.add(s.programmeEntryId)
  }
  chosen.sort((a, b) => a.startTime.localeCompare(b.startTime))
  const score = chosen.reduce((sum, s) => sum + weightOf(s, p), 0)
  return { status: "READY" as const, chosen, score }
}

function diff(
  draft: Screening[],
  active: Screening[],
  score: number,
  activeScore: number,
  tickets: Ticket[]
): DraftDiff {
  const inDraft = new Set(draft.map((s) => s.id))
  const inActive = new Set(active.map((s) => s.id))
  const removed = active.filter((s) => !inDraft.has(s.id))
  return {
    scoreDelta: score - activeScore,
    added: draft.filter((s) => !inActive.has(s.id)),
    removed,
    droppedTickets: removed.filter((s) =>
      tickets.some((t) => t.screening.id === s.id)
    ),
  }
}

function ticket(
  id: string,
  flags: Partial<Omit<Ticket, "screening">> = {}
): Ticket {
  return {
    screening: screening(id as ScreeningId),
    exchangeable: false,
    refundable: false,
    ...flags,
  }
}

function initial(): State {
  const inputs: PlanningInputs = {
    screeningCommitments: [
      "screening-2-1" as ScreeningId,
      "screening-11-2" as ScreeningId,
    ],
    filmCommitments: ["entry-3" as ProgrammeEntryId],
    excludedScreenings: [],
    excludedProgrammeEntries: [],
    preferences: {
      ...defaultPreferences,
      entryWeights: { ["entry-5" as ProgrammeEntryId]: 1.5 },
    },
  }
  const first = solve(inputs)
  return {
    inputs,
    schedules: [
      {
        id: "schedule-1" as ScheduleId,
        number: 1,
        score: first.score,
        acceptedAt: "2026-10-01T10:00:00+00:00",
        screenings: first.chosen,
      },
    ],
    drafts: [],
    tickets: [
      // Held: in the schedule.
      ticket("screening-2-1"),
      // Let go: another screening of a film the schedule has elsewhere.
      ticket("screening-1-2", { refundable: true }),
      // Let go: withdrawn.
      ticket("screening-11-2", { exchangeable: true }),
    ],
    nextId: 1,
  }
}

// Mirrors the backend's Flags, kind for kind.
function flags(state: State): Flag[] {
  const active = new Set(state.schedules.at(-1)?.screenings.map((s) => s.id))
  const flag = (kind: Flag["kind"], message: string, s: Screening): Flag => ({
    kind,
    message,
    screening: s,
    programmeEntryId: null,
  })
  const out: Flag[] = []
  for (const id of state.inputs.screeningCommitments) {
    const s = screening(id)
    if (s.withdrawn)
      out.push(
        flag("WITHDRAWN_COMMITMENT", "A committed Screening was withdrawn", s)
      )
  }
  for (const t of state.tickets) {
    if (t.screening.withdrawn)
      out.push(
        flag(
          "WITHDRAWN_TICKET",
          "A ticketed Screening was withdrawn",
          t.screening
        )
      )
    else if (!active.has(t.screening.id))
      out.push(
        flag(
          "UNSCHEDULED_TICKET",
          "A ticketed Screening is not in the Active Schedule",
          t.screening
        )
      )
  }
  for (const id of active) {
    const s = screening(id)
    if (s.withdrawn)
      out.push(
        flag("WITHDRAWN_IN_SCHEDULE", "A scheduled Screening was withdrawn", s)
      )
  }
  return out
}

function suggestions(state: State, scheduled: Screening[]): ComparisonPair[] {
  const entries = new Map(programme.map((e) => [e.id, e]))
  const inSchedule = new Set(scheduled.map((s) => s.programmeEntryId))
  const compared = (a: ProgrammeEntryId, b: ProgrammeEntryId) =>
    state.inputs.preferences.comparisons.some(
      (c) =>
        [c.preferredId, c.otherId].includes(a) &&
        [c.preferredId, c.otherId].includes(b)
    )
  const pairs: ComparisonPair[] = []
  for (const s of scheduled) {
    for (const other of programme) {
      if (inSchedule.has(other.id) || compared(s.programmeEntryId, other.id))
        continue
      if (other.screenings.some((o) => !fits([s], o, noBuffer))) {
        pairs.push({ scheduled: entries.get(s.programmeEntryId)!, other })
      }
    }
  }
  return pairs.slice(0, 10)
}

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms))

export function memoryPlanning(session: SessionPort): PlanningPort {
  let state = initial()

  const signedIn = () => {
    if (!session.token()) throw new PortError({ kind: "notSignedIn" })
  }
  const active = () => state.schedules.at(-1)!
  const find = (id: DraftId) => {
    const draft = state.drafts.find((d) => d.id === id)
    if (!draft) throw new PortError({ kind: "notFound" })
    return draft
  }
  const withDiff = (d: Draft): Draft =>
    d.status === "READY" && !d.stale
      ? {
          ...d,
          diff: diff(
            d.screenings,
            active().screenings,
            d.score,
            active().score,
            state.tickets
          ),
        }
      : d

  const startSolve = (draft: Draft) => {
    setTimeout(() => {
      const result = solve(apply(state.inputs, draft.changeSet))
      state = {
        ...state,
        drafts: state.drafts.map((d) =>
          d.id === draft.id
            ? {
                ...d,
                status: result.status,
                screenings: result.chosen,
                score: result.score,
                reasons:
                  result.status === "INFEASIBLE"
                    ? ["A committed film has no free screening."]
                    : [],
                stale: false,
              }
            : d
        ),
      }
    }, SOLVE_MS)
  }

  return {
    async planning() {
      await wait(120)
      if (!session.token()) return null
      const latest = [...state.drafts]
        .reverse()
        .find((d) => d.status === "READY")
      return {
        festivalId: festival.id,
        activeSchedule: active(),
        drafts: state.drafts.map(withDiff),
        inputs: state.inputs,
        flags: flags(state),
        tickets: state.tickets,
        suggestions: suggestions(
          state,
          latest?.screenings ?? active().screenings
        ),
      }
    },
    async draft(id) {
      await wait(80)
      signedIn()
      const d = state.drafts.find((x) => x.id === id)
      return d ? withDiff(d) : null
    },
    async createDraft(_festivalId, changeSet) {
      await wait(150)
      signedIn()
      const draft: Draft = {
        id: `draft-${state.nextId}` as DraftId,
        festivalId: festival.id,
        status: "SOLVING",
        stale: false,
        changeSet: [...changeSet],
        screenings: [],
        score: 0,
        reasons: [],
        notes: [],
        createdAt: new Date().toISOString(),
        diff: null,
      }
      state = {
        ...state,
        drafts: [...state.drafts, draft],
        nextId: state.nextId + 1,
      }
      startSolve(draft)
      return draft
    },
    async resolveDraft(id) {
      await wait(150)
      signedIn()
      const draft = { ...find(id), status: "SOLVING" as const }
      state = {
        ...state,
        drafts: state.drafts.map((d) => (d.id === id ? draft : d)),
      }
      startSolve(draft)
      return draft
    },
    async acceptDraft(id) {
      await wait(150)
      signedIn()
      const draft = find(id)
      if (draft.status !== "READY" || draft.stale) {
        throw new PortError({
          kind: "draftNotAcceptable",
          message: "Not ready or stale.",
        })
      }
      const inputs = apply(state.inputs, draft.changeSet)
      const schedule: Schedule = {
        id: `schedule-${state.schedules.length + 1}` as ScheduleId,
        number: state.schedules.length + 1,
        score: draft.score,
        acceptedAt: new Date().toISOString(),
        screenings: draft.screenings,
      }
      state = {
        ...state,
        inputs,
        schedules: [...state.schedules, schedule],
        drafts: state.drafts
          .filter((d) => d.id !== id)
          .map((d) => ({ ...d, stale: true })),
      }
      return schedule
    },
    async discardDraft(id) {
      await wait(80)
      signedIn()
      find(id)
      state = { ...state, drafts: state.drafts.filter((d) => d.id !== id) }
    },
    async recordTicket(id) {
      await wait(80)
      signedIn()
      if (!state.tickets.some((t) => t.screening.id === id)) {
        state = { ...state, tickets: [...state.tickets, ticket(id)] }
      }
    },
    async removeTicket(id) {
      await wait(80)
      signedIn()
      state = {
        ...state,
        tickets: state.tickets.filter((t) => t.screening.id !== id),
      }
    },
  }
}
