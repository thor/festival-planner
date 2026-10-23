// The ports the app drives. Adapters implement them; nothing else knows
// how data travels. Methods throw PortError.

import type { ChangeSet } from "./change-set"
import type {
  Draft,
  DraftId,
  Festival,
  FestivalId,
  Planning,
  ProgrammeEntry,
  ProgrammeEntryId,
  Schedule,
  ScreeningId,
} from "./model"

export interface ProgrammePort {
  festivals(): Promise<Festival[]>
  festival(slug: string): Promise<Festival | null>
  /** Every Programme Entry with its Screenings, by title. */
  programme(festivalId: FestivalId): Promise<ProgrammeEntry[]>
  entry(id: ProgrammeEntryId): Promise<ProgrammeEntry | null>
}

export interface PlanningPort {
  /** Null when signed out. */
  planning(festivalId: FestivalId): Promise<Planning | null>
  draft(id: DraftId): Promise<Draft | null>
  createDraft(festivalId: FestivalId, changeSet: ChangeSet): Promise<Draft>
  resolveDraft(id: DraftId): Promise<Draft>
  acceptDraft(id: DraftId): Promise<Schedule>
  discardDraft(id: DraftId): Promise<void>
  recordTicket(id: ScreeningId): Promise<void>
  removeTicket(id: ScreeningId): Promise<void>
}

export interface SessionPort {
  token(): string | null
  signIn(token: string): void
  signOut(): void
  subscribe(listener: () => void): () => void
}

export interface Ports {
  programme: ProgrammePort
  planning: PlanningPort
  session: SessionPort
}
