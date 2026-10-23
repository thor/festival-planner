// Port reads as cached queries. Keys live here and nowhere else.

import { useQuery } from "@tanstack/react-query"

import type {
  DraftId,
  Festival,
  FestivalId,
  ProgrammeEntryId,
} from "@/domain/model"

import { usePorts } from "./ports"
import { useSignedIn } from "./session"

export const keys = {
  festivals: ["festivals"] as const,
  festival: (slug: string) => ["festival", slug] as const,
  programme: (id: FestivalId) => ["programme", id] as const,
  entry: (id: ProgrammeEntryId) => ["entry", id] as const,
  planning: (id: FestivalId) => ["planning", id] as const,
  draft: (id: DraftId) => ["planning", "draft", id] as const,
}

export function useFestivals() {
  const { programme } = usePorts()
  return useQuery({
    queryKey: keys.festivals,
    queryFn: () => programme.festivals(),
  })
}

export function useFestival(slug: string) {
  const { programme } = usePorts()
  return useQuery({
    queryKey: keys.festival(slug),
    queryFn: () => programme.festival(slug),
  })
}

export function useProgramme(festival: Festival | null | undefined) {
  const { programme } = usePorts()
  return useQuery({
    queryKey: keys.programme(festival?.id as FestivalId),
    queryFn: () => programme.programme(festival!.id),
    enabled: !!festival,
    staleTime: 5 * 60_000,
  })
}

export function usePlanning(festival: Festival | null | undefined) {
  const { planning } = usePorts()
  const signedIn = useSignedIn()
  return useQuery({
    queryKey: [...keys.planning(festival?.id as FestivalId), signedIn],
    queryFn: () => planning.planning(festival!.id),
    enabled: !!festival,
  })
}

export function useDraft(id: DraftId) {
  const { planning } = usePorts()
  return useQuery({
    queryKey: keys.draft(id),
    queryFn: () => planning.draft(id),
    // Poll while the solver works, as the API asks.
    refetchInterval: (q) => (q.state.data?.status === "SOLVING" ? 700 : false),
  })
}
