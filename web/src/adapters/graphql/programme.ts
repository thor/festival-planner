import type { ResultOf } from "gql.tada"

import type { ProgrammeEntry, ProgrammeEntryId } from "@/domain/model"
import type { ProgrammePort } from "@/domain/ports"

import type { Run } from "./client"
import { EntryQuery, FestivalQuery, FestivalsQuery, ProgrammePageQuery } from "./documents"
import { entryOf, festivalOf } from "./mapping"

export function graphqlProgramme(run: Run): ProgrammePort {
  return {
    async festivals() {
      const data = await run(FestivalsQuery, {})
      return data.festivals.map(festivalOf)
    },
    async festival(slug) {
      const data = await run(FestivalQuery, { slug })
      return data.festival ? festivalOf(data.festival) : null
    },
    async programme(id) {
      // The API caps pages at 100.
      const entries: ProgrammeEntry[] = []
      let after: string | null = null
      for (;;) {
        const data: ResultOf<typeof ProgrammePageQuery> = await run(ProgrammePageQuery, { id, after })
        const page = data.node && "programmeEntries" in data.node ? data.node.programmeEntries : null
        if (!page) return entries
        entries.push(...page.edges.map((e) => entryOf(e.node)))
        if (!page.pageInfo.hasNextPage) return entries
        after = page.pageInfo.endCursor
      }
    },
    async entry(id: ProgrammeEntryId) {
      const data = await run(EntryQuery, { id })
      return data.node && "title" in data.node ? entryOf(data.node) : null
    },
  }
}
