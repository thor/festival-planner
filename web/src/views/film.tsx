import {
  ArrowSquareOutIcon,
  PlusIcon,
  TicketIcon,
  XIcon,
} from "@phosphor-icons/react"

import type { EntryVM, FilmVM, ScreeningVM } from "@/app/view-models"
import { cn } from "@/lib/utils"

import { Docked } from "./dock"
import { Action, ExternalLink, Meta, Page } from "./parts"
import { ScreeningRow } from "./screening-row"

export function FilmView({ vm }: { vm: FilmVM }) {
  const { entry } = vm
  return (
    <Page>
      <header className="border-b border-ink pt-10 pb-8 md:pt-20 md:pb-12">
        <h1
          className={cn(
            "title text-[clamp(3.3rem,11vw,11rem)]",
            entry.marks.committed && "text-stamp",
            entry.marks.excluded && "text-grain line-through decoration-2"
          )}
        >
          {vm.title}
        </h1>
        <div className="mt-6 flex flex-wrap items-center justify-between gap-4">
          <Meta items={vm.meta} className="text-lg" />
          <FilmActions entry={entry} url={vm.url} />
        </div>
      </header>

      <div className="md:grid md:grid-cols-[minmax(0,42rem)_1fr] md:gap-10">
        <ul className="pt-4">
          {entry.screenings.map((s) => (
            <ScreeningRow key={s.id} s={s} withTicket />
          ))}
        </ul>
        {vm.buy && (
          <>
            {/* Wide: beside the screenings, kept in view. */}
            <aside className="sticky top-14 hidden self-start pt-4 md:block">
              <BuyTicket
                buy={vm.buy}
                className="max-w-sm flex-col items-start gap-1 px-5 py-4"
              />
            </aside>
            {/* Narrow: along the bottom edge. */}
            <Docked>
              <BuyTicket
                buy={vm.buy}
                className="h-14 items-center justify-between gap-4 px-4 md:hidden"
              />
            </Docked>
          </>
        )}
      </div>
    </Page>
  )
}

function BuyTicket({
  buy,
  className,
}: {
  buy: ScreeningVM
  className: string
}) {
  return (
    <ExternalLink
      href={buy.buyHref!}
      className={cn(
        "flex w-full bg-stamp text-stamp-ink hover:bg-stamp/85",
        className
      )}
    >
      <span className="flex items-center gap-3 text-lg">
        <TicketIcon size={22} weight="light" />
        Buy ticket
      </span>
      <span className="truncate opacity-80">
        {buy.day} {buy.time} {buy.venue}
      </span>
    </ExternalLink>
  )
}

function FilmActions({ entry, url }: { entry: EntryVM; url: string | null }) {
  return (
    <div className="flex">
      <Action
        icon={PlusIcon}
        label={entry.marks.committed ? "Release film" : "Commit to film"}
        on={entry.marks.committed}
        tone="stamp"
        onClick={entry.onCommit}
      />
      <Action
        icon={XIcon}
        label={entry.marks.excluded ? "Include film" : "Exclude film"}
        on={entry.marks.excluded}
        onClick={entry.onExclude}
        className="-ml-px"
      />
      {url && (
        <Action
          icon={ArrowSquareOutIcon}
          label="Festival page"
          href={url}
          className="-ml-px"
        />
      )}
    </div>
  )
}
