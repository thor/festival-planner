// The composition root: the one place that picks adapters.

import { browserSession } from "@/adapters/browser/session"
import { graphqlClient } from "@/adapters/graphql/client"
import { graphqlPlanning } from "@/adapters/graphql/planning"
import { graphqlProgramme } from "@/adapters/graphql/programme"
import { memoryPlanning } from "@/adapters/memory/planning"
import { memoryProgramme } from "@/adapters/memory/programme"
import { memorySession } from "@/adapters/memory/session"
import type { Ports } from "@/domain/ports"

export type AdapterName = "memory" | "graphql"

export function adapterName(): AdapterName {
  return import.meta.env.VITE_ADAPTER === "graphql" ? "graphql" : "memory"
}

export function composePorts(name: AdapterName = adapterName()): Ports {
  if (name === "graphql") {
    const session = browserSession()
    const run = graphqlClient(import.meta.env.VITE_GRAPHQL_URL ?? "/graphql", session)
    return { session, programme: graphqlProgramme(run), planning: graphqlPlanning(run) }
  }
  const session = memorySession()
  return { session, programme: memoryProgramme(), planning: memoryPlanning(session) }
}
