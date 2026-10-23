import { PortError, type PortProblem } from "@/domain/errors"
import type { ComparisonPair, ProgrammeEntryId } from "@/domain/model"
import type { PlanningPort } from "@/domain/ports"

import type { Run } from "./client"
import {
  AcceptDraftMutation,
  CreateDraftMutation,
  DiscardDraftMutation,
  DraftQuery,
  PlanningQuery,
  RecordTicketMutation,
  RemoveTicketMutation,
  ResolveDraftMutation,
} from "./documents"
import {
  draftOf,
  flagOf,
  inputsOf,
  itemInputOf,
  scheduleOf,
  screeningOf,
} from "./mapping"

type Failure =
  | { __typename: "NotSignedIn" }
  | { __typename: "NotFound" }
  | { __typename: "DraftStillSolving" }
  | { __typename: "DraftNotAcceptable"; message?: string }
  | {
      __typename: "InvalidChangeSet"
      problems?: { message: string; items: number[] }[]
    }

/** Turn a mutation's error member into a PortError. */
function fail(result: Failure): never {
  const problems: Record<Failure["__typename"], PortProblem> = {
    NotSignedIn: { kind: "notSignedIn" },
    NotFound: { kind: "notFound" },
    DraftStillSolving: { kind: "draftStillSolving" },
    DraftNotAcceptable: {
      kind: "draftNotAcceptable",
      message: "message" in result ? (result.message ?? "") : "",
    },
    InvalidChangeSet: {
      kind: "invalidChangeSet",
      problems: "problems" in result ? (result.problems ?? []) : [],
    },
  }
  throw new PortError(problems[result.__typename])
}

const ok = (typename: string, expected: string, result: unknown) => {
  if (typename !== expected) fail(result as Failure)
}

export function graphqlPlanning(run: Run): PlanningPort {
  return {
    async planning(festivalId) {
      const { viewer } = await run(PlanningQuery, { festivalId })
      const p = viewer?.planning
      if (!viewer || !p) return null
      return {
        festivalId,
        activeSchedule: p.activeSchedule ? scheduleOf(p.activeSchedule) : null,
        drafts: p.drafts.map((d) => draftOf(d)),
        inputs: inputsOf(p.inputs),
        flags: p.flags.map(flagOf),
        tickets: viewer.tickets.map((t) => ({
          screening: screeningOf(t.screening),
          exchangeable: t.exchangeable,
          refundable: t.refundable,
        })),
        suggestions: p.comparisonSuggestions.map((s): ComparisonPair => ({
          scheduledId: s.scheduled.id as ProgrammeEntryId,
          otherId: s.other.id as ProgrammeEntryId,
        })),
      }
    },
    async draft(id) {
      const { node } = await run(DraftQuery, { id })
      if (!node || !("status" in node)) return null
      const diff = node.diff && {
        scoreDelta: node.diff.scoreDelta,
        added: node.diff.added.map(screeningOf),
        removed: node.diff.removed.map(screeningOf),
        droppedTickets: node.diff.droppedTickets.map(screeningOf),
      }
      return draftOf(node, diff)
    },
    async createDraft(festivalId, changeSet) {
      const items = changeSet.map(itemInputOf)
      const { createDraft: r } = await run(
        CreateDraftMutation,
        { input: { festivalId, changeSet: items } },
        "mutation"
      )
      if (r.__typename !== "DraftResult") fail(r)
      return draftOf(r.draft)
    },
    async resolveDraft(id) {
      const { resolveDraft: r } = await run(
        ResolveDraftMutation,
        { input: { draftId: id } },
        "mutation"
      )
      if (r.__typename !== "DraftResult") fail(r as Failure)
      return draftOf(r.draft)
    },
    async acceptDraft(id) {
      const { acceptDraft: r } = await run(
        AcceptDraftMutation,
        { input: { draftId: id } },
        "mutation"
      )
      if (r.__typename !== "ScheduleResult") fail(r as Failure)
      return scheduleOf(r.schedule)
    },
    async discardDraft(id) {
      const { discardDraft: r } = await run(
        DiscardDraftMutation,
        { input: { draftId: id } },
        "mutation"
      )
      ok(r.__typename, "Discarded", r)
    },
    async recordTicket(id) {
      const { recordTicket: r } = await run(
        RecordTicketMutation,
        { input: { screeningId: id } },
        "mutation"
      )
      ok(r.__typename, "TicketResult", r)
    },
    async removeTicket(id) {
      const { removeTicket: r } = await run(
        RemoveTicketMutation,
        { input: { screeningId: id } },
        "mutation"
      )
      ok(r.__typename, "ScreeningResult", r)
    },
  }
}
