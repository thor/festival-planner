import { ArrowSquareOutIcon, PlusIcon, XIcon } from "@phosphor-icons/react"

import type { FilmVM } from "@/app/view-models"
import { cn } from "@/lib/utils"

import { Action, Meta, Page } from "./parts"
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
            entry.marks.excluded && "text-grain line-through decoration-2",
          )}
        >
          {vm.title}
        </h1>
        <div className="mt-6 flex flex-wrap items-center justify-between gap-4">
          <Meta items={vm.meta} className="text-lg" />
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
            {vm.url && (
              <a
                href={vm.url}
                target="_blank"
                rel="noreferrer"
                aria-label="Festival page"
                className="-ml-px flex size-8 items-center justify-center border border-ink hover:bg-haze"
              >
                <ArrowSquareOutIcon size={18} weight="light" />
              </a>
            )}
          </div>
        </div>
      </header>
      <ul className="max-w-2xl pt-4">
        {entry.screenings.map((s) => (
          <ScreeningRow key={s.id} s={s} withTicket />
        ))}
      </ul>
    </Page>
  )
}
