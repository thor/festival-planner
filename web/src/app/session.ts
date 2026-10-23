import { useQueryClient } from "@tanstack/react-query"
import { useSyncExternalStore, type FormEvent } from "react"

import { adapterName } from "./composition"
import { usePorts } from "./ports"

export function useSignedIn(): boolean {
  const { session } = usePorts()
  return useSyncExternalStore(session.subscribe, () => session.token() !== null)
}

export function useSession() {
  const { session } = usePorts()
  const client = useQueryClient()
  const signedIn = useSignedIn()
  const reset = () => client.invalidateQueries({ queryKey: ["planning"] })
  return {
    signedIn,
    /** The memory adapter takes any token. */
    hint:
      adapterName() === "memory"
        ? "Any text works here."
        : "festival-planner token issue",
    /** For a form with a `token` field. */
    onSubmit(event: FormEvent<HTMLFormElement>) {
      event.preventDefault()
      session.signIn(
        String(new FormData(event.currentTarget).get("token") ?? "")
      )
      void reset()
    },
    signOut() {
      session.signOut()
      void reset()
    },
  }
}
