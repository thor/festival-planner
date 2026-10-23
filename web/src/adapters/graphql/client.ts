import {
  Client,
  fetchExchange,
  type AnyVariables,
  type TypedDocumentNode,
} from "@urql/core"

import { PortError } from "@/domain/errors"
import type { SessionPort } from "@/domain/ports"

export type Run = <Data, Variables extends AnyVariables>(
  document: TypedDocumentNode<Data, Variables>,
  variables: Variables,
  kind?: "query" | "mutation"
) => Promise<Data>

/**
 * One urql client per app. Caching is the app layer's job, so every request
 * goes to the network. A 401 means the token is bad: sign out.
 */
export function graphqlClient(url: string, session: SessionPort): Run {
  const client = new Client({
    url,
    exchanges: [fetchExchange],
    requestPolicy: "network-only",
    preferGetMethod: false,
    fetchOptions: () => {
      const token = session.token()
      const headers: Record<string, string> = {}
      if (token) headers.authorization = `Bearer ${token}`
      return { headers }
    },
    fetch: async (input, init) => {
      const response = await fetch(input, init)
      if (response.status === 401) {
        session.signOut()
        throw new PortError({ kind: "notSignedIn" })
      }
      return response
    },
  })

  return async (document, variables, kind = "query") => {
    const result =
      kind === "query"
        ? await client.query(document, variables).toPromise()
        : await client.mutation(document, variables).toPromise()
    if (result.error?.networkError instanceof PortError)
      throw result.error.networkError
    if (result.error || !result.data) {
      throw new PortError({
        kind: "unreachable",
        message: result.error?.message ?? "No data",
      })
    }
    return result.data
  }
}
