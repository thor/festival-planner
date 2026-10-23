import { MinusIcon, PlusIcon, TicketIcon, WarningIcon } from "@phosphor-icons/react"
import { Link } from "react-router"

import type { DiffRowVM, DraftListItemVM, DraftVM } from "@/app/view-models"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

import { ItemLine } from "./items"
import { Page, Spinner } from "./parts"

const statusWord: Record<DraftVM["status"], string> = {
  solving: "Solving",
  ready: "Ready",
  infeasible: "Nothing fits",
  failed: "Failed",
}

export function DraftListView({ drafts }: { drafts: DraftListItemVM[] }) {
  if (drafts.length === 0) {
    return (
      <Page className="py-16">
        <p className="text-xl">No drafts. Change something, then solve.</p>
      </Page>
    )
  }
  return (
    <Page>
      <h1 className="border-b border-ink py-6 text-xl">Drafts</h1>
      <ol>
        {drafts.map((d) => (
          <li key={d.id} className="border-b border-ink">
            <Link to={d.href} className="grid grid-cols-[4rem_1fr_auto] items-baseline gap-4 py-4 hover:bg-haze">
              <span>{d.created}</span>
              <span>
                {d.stale ? "Out of date" : statusWord[d.status]}
              </span>
              <span className="text-grain">
                {d.changes} {d.changes === 1 ? "change" : "changes"}
              </span>
            </Link>
          </li>
        ))}
      </ol>
    </Page>
  )
}

export function DraftView({ vm }: { vm: DraftVM }) {
  const canAccept = vm.status === "ready" && !vm.stale && !vm.busy
  return (
    <Page>
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-ink py-6">
        <div className="flex items-baseline gap-6">
          {vm.status === "solving" ? (
            <Spinner label="Solving" />
          ) : (
            <h1 className="text-xl">{vm.stale ? "Out of date" : statusWord[vm.status]}</h1>
          )}
          {vm.scoreDelta && (
            <span aria-label="Score change" className="text-xl text-grain">
              {vm.scoreDelta}
            </span>
          )}
        </div>
        <div className="flex gap-2">
          <Button variant="outline" className="h-10 px-4 text-base" disabled={vm.busy} onClick={vm.onDiscard}>
            Discard
          </Button>
          {(vm.stale || vm.status === "failed" || vm.status === "infeasible") && (
            <Button variant="outline" className="h-10 px-4 text-base" disabled={vm.busy} onClick={vm.onResolve}>
              Solve again
            </Button>
          )}
          <Button className="h-10 px-5 text-base" disabled={!canAccept} onClick={vm.onAccept}>
            Accept
          </Button>
        </div>
      </header>

      {vm.error && <p className="border-b border-ink py-3">{vm.error}</p>}
      {vm.reasons.map((r) => (
        <p key={r} className="border-b border-ink py-3">
          {r}
        </p>
      ))}
      {vm.droppedTickets > 0 && (
        <p className="flex items-center gap-2 border-b border-ink py-3">
          <WarningIcon size={18} weight="light" />
          Drops {vm.droppedTickets} {vm.droppedTickets === 1 ? "ticket" : "tickets"}.
        </p>
      )}

      <div className="grid gap-x-10 md:grid-cols-2">
        <DiffList rows={vm.added} sign="plus" empty="Nothing added." />
        <DiffList rows={vm.removed} sign="minus" empty="Nothing removed." />
      </div>

      {vm.items.length > 0 && (
        <section className="mt-10 max-w-xl">
          <h2 className="border-b border-ink pb-2 text-grain">Changes</h2>
          <ul>
            {vm.items.map((item, i) => (
              <ItemLine key={i} item={item} />
            ))}
          </ul>
        </section>
      )}
    </Page>
  )
}

function DiffList({ rows, sign, empty }: { rows: DiffRowVM[]; sign: "plus" | "minus"; empty: string }) {
  const Glyph = sign === "plus" ? PlusIcon : MinusIcon
  return (
    <ul aria-label={sign === "plus" ? "Added" : "Removed"}>
      {rows.length === 0 && <li className="border-b border-ink py-4 text-grain">{empty}</li>}
      {rows.map((r) => (
        <li key={r.id} className="grid grid-cols-[1.5rem_1fr] gap-x-3 border-b border-ink py-4">
          <Glyph size={20} weight="light" className={cn("mt-1", sign === "plus" && "text-stamp")} />
          <div>
            <p className={cn("title text-2xl", sign === "minus" && "text-grain")}>{r.title}</p>
            <p className="mt-2 flex items-center gap-4 text-grain">
              <span>{r.when}</span>
              <span>{r.venue}</span>
              {r.ticket && <TicketIcon size={16} weight="bold" aria-label="Ticket" className="text-ink" />}
            </p>
          </div>
        </li>
      ))}
    </ul>
  )
}
