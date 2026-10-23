import {
  ArrowSquareOutIcon,
  PlusIcon,
  TicketIcon,
  XIcon,
} from "@phosphor-icons/react"

import type {
  EntryVM,
  FactVM,
  FilmVM,
  ImageVM,
  ScreeningVM,
} from "@/app/view-models"
import { cn } from "@/lib/utils"

import { Docked } from "./dock"
import { InterestControl } from "./interest"
import { Action, ExternalLink, Meta, Page, Place } from "./parts"
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
        {vm.tagline && (
          <p className="mt-6 max-w-[46ch] text-lg md:text-xl">{vm.tagline}</p>
        )}
        <div className="mt-6 flex flex-wrap items-center justify-between gap-4">
          <Meta items={vm.meta} className="text-lg" />
          <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
            <InterestControl vm={vm.interest} size="sm" />
            <FilmActions entry={entry} url={vm.url} />
          </div>
        </div>
      </header>

      {vm.still && <Still image={vm.still} />}

      <div className="md:grid md:grid-cols-[minmax(0,42rem)_1fr] md:gap-10">
        <ul className="pt-4">
          {entry.screenings.map((s) => (
            <ScreeningRow key={s.id} s={s} withTicket />
          ))}
        </ul>
        {vm.buy && (
          <>
            {/* Wide: beside the screenings, kept in view. */}
            <aside className="sticky top-[calc(var(--spacing-bar)+1rem)] hidden self-start pt-4 md:block">
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

      {(vm.paragraphs.length > 0 || vm.facts.length > 0 || vm.poster) && (
        <About vm={vm} />
      )}
    </Page>
  )
}

/**
 * A frame from the film, letterboxed like the screen it was made for and
 * printed in silver: colour is kept for what is yours.
 */
function Still({ image }: { image: ImageVM }) {
  return (
    <figure className="border-b border-ink py-6 md:py-8">
      <div className="aspect-[2.39/1] overflow-hidden bg-haze">
        <img
          src={image.src}
          alt={image.alt}
          loading="lazy"
          className="size-full object-cover contrast-[1.05] grayscale dark:brightness-[0.8]"
        />
      </div>
    </figure>
  )
}

/** The Festival's words on the left; the facts, and a poster, on the right. */
function About({ vm }: { vm: FilmVM }) {
  return (
    <section
      aria-label="About the film"
      className="mt-12 grid gap-10 border-t border-ink pt-8 md:grid-cols-[minmax(0,42rem)_1fr] md:pt-10"
    >
      {vm.paragraphs.length > 0 && (
        <div className="max-w-[65ch] space-y-4 leading-relaxed md:text-lg">
          {vm.paragraphs.map((p, i) => (
            <p key={i}>{p}</p>
          ))}
          {vm.credit && <p className="text-grain">{vm.credit}</p>}
        </div>
      )}
      <div className="flex flex-col gap-8 self-start">
        {vm.poster && (
          <img
            src={vm.poster.src}
            alt={vm.poster.alt}
            loading="lazy"
            className="w-full max-w-56 border border-ink grayscale dark:brightness-[0.8]"
          />
        )}
        {vm.facts.length > 0 && <Facts facts={vm.facts} />}
      </div>
    </section>
  )
}

function Facts({ facts }: { facts: FactVM[] }) {
  return (
    <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-6">
      {facts.map((f) => (
        <div
          key={f.label}
          className="col-span-2 grid grid-cols-subgrid border-t border-haze py-2 first:border-t-0 first:pt-0"
        >
          <dt className="text-grain">{f.label}</dt>
          <dd>
            {f.href ? (
              <ExternalLink
                href={f.href}
                className="underline underline-offset-4 hover:text-stamp"
              >
                {f.value}
              </ExternalLink>
            ) : (
              f.value
            )}
          </dd>
        </div>
      ))}
    </dl>
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
        {buy.day} {buy.time}{" "}
        <Place venue={buy.venue} auditorium={buy.auditorium} />
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
