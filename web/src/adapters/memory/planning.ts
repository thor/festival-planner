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
  ProgrammeEntryId,
  Schedule,
  ScheduleId,
  Screening,
  ScreeningId,
  Ticket,
} from "@/domain/model"
import type { PlanningPort, SessionPort } from "@/domain/ports"

import { festival, programme } from "./seed"

const SOLVE_MS = 900

const all = programme.flatMap((e) => e.screenings)
const byId = new Map(all.map((s) => [s.id, s]))
const screening = (id: ScreeningId) => byId.get(id)!

interface Comparison {
  preferredId: ProgrammeEntryId
  otherId: ProgrammeEntryId
}

interface State {
  inputs: PlanningInputs
  comparisons: Comparison[]
  schedules: Schedule[]
  drafts: Draft[]
  tickets: Ticket[]
  nextId: number
}

function apply(inputs: PlanningInputs, comparisons: Comparison[], set: ChangeSet) {
  const next: PlanningInputs = {
    screeningCommitments: [...inputs.screeningCommitments],
    filmCommitments: [...inputs.filmCommitments],
    excludedScreenings: [...inputs.excludedScreenings],
    excludedProgrammeEntries: [...inputs.excludedProgrammeEntries],
    bufferMinutes: inputs.bufferMinutes,
  }
  let compared = [...comparisons]
  const add = <T>(list: T[], v: T) => (list.includes(v) ? list : [...list, v])
  const drop = <T>(list: T[], v: T) => list.filter((x) => x !== v)
  for (const item of set) {
    switch (item.kind) {
      case "addScreeningCommitment":
        next.screeningCommitments = add(next.screeningCommitments, item.screeningId)
        break
      case "releaseScreeningCommitment":
        next.screeningCommitments = drop(next.screeningCommitments, item.screeningId)
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
        next.excludedScreenings = drop(next.excludedScreenings, item.screeningId)
        break
      case "addExcludedProgrammeEntry":
        next.excludedProgrammeEntries = add(next.excludedProgrammeEntries, item.programmeEntryId)
        break
      case "removeExcludedProgrammeEntry":
        next.excludedProgrammeEntries = drop(next.excludedProgrammeEntries, item.programmeEntryId)
        break
      case "recordComparison":
        compared = [
          ...compared.filter(
            (c) =>
              !(
                [c.preferredId, c.otherId].includes(item.preferredId) &&
                [c.preferredId, c.otherId].includes(item.otherId)
              ),
          ),
          { preferredId: item.preferredId, otherId: item.otherId },
        ]
        break
      case "setBuffer":
        next.bufferMinutes = item.minutes ?? 15
        break
      case "other":
        break
    }
  }
  return { inputs: next, comparisons: compared }
}

function weightOf(entry: ProgrammeEntryId, comparisons: Comparison[]): number {
  let w = 1
  for (const c of comparisons) {
    if (c.preferredId === entry) w += 0.25
    if (c.otherId === entry) w -= 0.25
  }
  return w
}

function fits(chosen: Screening[], s: Screening, buffer: number): boolean {
  const gap = buffer * 60000
  return chosen.every(
    (c) =>
      Date.parse(c.endTime) + gap <= Date.parse(s.startTime) ||
      Date.parse(s.endTime) + gap <= Date.parse(c.startTime),
  )
}

function solve(inputs: PlanningInputs, comparisons: Comparison[]) {
  const buffer = inputs.bufferMinutes
  const chosen: Screening[] = inputs.screeningCommitments.map(screening)
  const done = new Set(chosen.map((s) => s.programmeEntryId))
  const open = (s: Screening) =>
    !s.withdrawn && !inputs.excludedScreenings.includes(s.id) && fits(chosen, s, buffer)

  for (const entryId of inputs.filmCommitments) {
    if (done.has(entryId)) continue
    const pick = programme.find((e) => e.id === entryId)?.screenings.find(open)
    if (!pick) return { status: "INFEASIBLE" as const, chosen: [], score: 0 }
    chosen.push(pick)
    done.add(entryId)
  }
  const rest = programme
    .filter((e) => !done.has(e.id) && !inputs.excludedProgrammeEntries.includes(e.id))
    .sort((a, b) => weightOf(b.id, comparisons) - weightOf(a.id, comparisons))
  for (const entry of rest) {
    const pick = entry.screenings.find(open)
    if (pick) chosen.push(pick)
  }
  chosen.sort((a, b) => a.startTime.localeCompare(b.startTime))
  const score = chosen.reduce((sum, s) => sum + weightOf(s.programmeEntryId, comparisons), 0)
  return { status: "READY" as const, chosen, score }
}

function diff(draft: Screening[], active: Screening[], score: number, activeScore: number, tickets: Ticket[]): DraftDiff {
  const inDraft = new Set(draft.map((s) => s.id))
  const inActive = new Set(active.map((s) => s.id))
  const removed = active.filter((s) => !inDraft.has(s.id))
  return {
    scoreDelta: score - activeScore,
    added: draft.filter((s) => !inActive.has(s.id)),
    removed,
    droppedTickets: removed.filter((s) => tickets.some((t) => t.screeningId === s.id)),
  }
}

function initial(): State {
  const inputs: PlanningInputs = {
    screeningCommitments: ["screening-2-1" as ScreeningId, "screening-11-2" as ScreeningId],
    filmCommitments: ["entry-3" as ProgrammeEntryId],
    excludedScreenings: [],
    excludedProgrammeEntries: [],
    bufferMinutes: 15,
  }
  const first = solve(inputs, [])
  return {
    inputs,
    comparisons: [],
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
    tickets: [{ screeningId: "screening-2-1" as ScreeningId, exchangeable: false, refundable: false }],
    nextId: 1,
  }
}

function flags(state: State): Flag[] {
  const out: Flag[] = []
  const active = state.schedules.at(-1)
  for (const id of state.inputs.screeningCommitments) {
    const s = screening(id)
    if (s.withdrawn) out.push({ kind: "WITHDRAWN_COMMITMENT", message: `${s.title} was withdrawn.`, screeningId: id, programmeEntryId: null })
  }
  for (const t of state.tickets) {
    if (!active?.screenings.some((s) => s.id === t.screeningId)) {
      const s = screening(t.screeningId)
      out.push({ kind: "UNSCHEDULED_TICKET", message: `Ticket for ${s.title} is not in the schedule.`, screeningId: s.id, programmeEntryId: null })
    }
  }
  return out
}

function suggestions(state: State, scheduled: Screening[]): ComparisonPair[] {
  const entries = new Map(programme.map((e) => [e.id, e]))
  const inSchedule = new Set(scheduled.map((s) => s.programmeEntryId))
  const compared = (a: ProgrammeEntryId, b: ProgrammeEntryId) =>
    state.comparisons.some((c) => [c.preferredId, c.otherId].includes(a) && [c.preferredId, c.otherId].includes(b))
  const pairs: ComparisonPair[] = []
  for (const s of scheduled) {
    for (const other of programme) {
      if (inSchedule.has(other.id) || compared(s.programmeEntryId, other.id)) continue
      if (other.screenings.some((o) => !fits([s], o, 0))) {
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
      ? { ...d, diff: diff(d.screenings, active().screenings, d.score, active().score, state.tickets) }
      : d

  const startSolve = (draft: Draft) => {
    setTimeout(() => {
      const applied = apply(state.inputs, state.comparisons, draft.changeSet)
      const result = solve(applied.inputs, applied.comparisons)
      state = {
        ...state,
        drafts: state.drafts.map((d) =>
          d.id === draft.id
            ? {
                ...d,
                status: result.status,
                screenings: result.chosen,
                score: result.score,
                reasons: result.status === "INFEASIBLE" ? ["A committed film has no free screening."] : [],
                stale: false,
              }
            : d,
        ),
      }
    }, SOLVE_MS)
  }

  return {
    async planning() {
      await wait(120)
      if (!session.token()) return null
      const latest = [...state.drafts].reverse().find((d) => d.status === "READY")
      return {
        festivalId: festival.id,
        activeSchedule: active(),
        drafts: state.drafts.map(withDiff),
        inputs: state.inputs,
        flags: flags(state),
        tickets: state.tickets,
        suggestions: suggestions(state, latest?.screenings ?? active().screenings),
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
      state = { ...state, drafts: [...state.drafts, draft], nextId: state.nextId + 1 }
      startSolve(draft)
      return draft
    },
    async resolveDraft(id) {
      await wait(150)
      signedIn()
      const draft = { ...find(id), status: "SOLVING" as const }
      state = { ...state, drafts: state.drafts.map((d) => (d.id === id ? draft : d)) }
      startSolve(draft)
      return draft
    },
    async acceptDraft(id) {
      await wait(150)
      signedIn()
      const draft = find(id)
      if (draft.status !== "READY" || draft.stale) {
        throw new PortError({ kind: "draftNotAcceptable", message: "Not ready or stale." })
      }
      const applied = apply(state.inputs, state.comparisons, draft.changeSet)
      const schedule: Schedule = {
        id: `schedule-${state.schedules.length + 1}` as ScheduleId,
        number: state.schedules.length + 1,
        score: draft.score,
        acceptedAt: new Date().toISOString(),
        screenings: draft.screenings,
      }
      state = {
        ...state,
        inputs: applied.inputs,
        comparisons: applied.comparisons,
        schedules: [...state.schedules, schedule],
        drafts: state.drafts.filter((d) => d.id !== id).map((d) => ({ ...d, stale: true })),
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
      if (!state.tickets.some((t) => t.screeningId === id)) {
        state = { ...state, tickets: [...state.tickets, { screeningId: id, exchangeable: false, refundable: false }] }
      }
    },
    async removeTicket(id) {
      await wait(80)
      signedIn()
      state = { ...state, tickets: state.tickets.filter((t) => t.screeningId !== id) }
    },
  }
}
