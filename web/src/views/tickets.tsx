import { Link } from "react-router"

import type { TicketsVM, TicketVM } from "@/app/view-models"
import { Button, buttonVariants } from "@/components/ui/button"
import { cn } from "@/lib/utils"

import { ExternalLink, Page, Place } from "./parts"

/** Tickets to let go on top, the rest below. Letting go is its own job. */
export function TicketsView({ vm }: { vm: TicketsVM }) {
  if (vm.letGo.length === 0 && vm.held.length === 0) {
    return (
      <Page className="py-16">
        <p className="text-xl">No tickets.</p>
        <Link
          to={vm.programmeHref}
          className="mt-4 inline-block underline underline-offset-4"
        >
          Programme
        </Link>
      </Page>
    )
  }
  return (
    <Page>
      <h1 className="sr-only">Tickets</h1>
      {vm.letGo.length > 0 && (
        <Section title="Let go" count={vm.letGo.length}>
          {vm.letGo.map((t) => (
            <LetGoRow key={t.id} t={t} />
          ))}
        </Section>
      )}
      {vm.held.length > 0 && (
        <Section
          title="Held"
          count={vm.held.length}
          className={cn(vm.letGo.length > 0 && "mt-12")}
        >
          {vm.held.map((t) => (
            <li
              key={t.id}
              className="grid gap-1 border-b border-ink py-4 md:grid-cols-[1fr_auto] md:items-baseline md:gap-8"
            >
              <Link to={t.href} className="title text-2xl hover:text-stamp">
                {t.title}
              </Link>
              <When t={t} />
            </li>
          ))}
        </Section>
      )}
    </Page>
  )
}

function Section({
  title,
  count,
  className,
  children,
}: {
  title: string
  count: number
  className?: string
  children: React.ReactNode
}) {
  return (
    <section aria-label={title} className={className}>
      <header className="flex items-baseline justify-between border-b border-ink py-6">
        <h2 className="text-xl">{title}</h2>
        <span className="text-grain">{count}</span>
      </header>
      <ul>{children}</ul>
    </section>
  )
}

function When({ t }: { t: TicketVM }) {
  return (
    <p className="flex gap-4 text-grain">
      <span>{t.when}</span>
      <Place venue={t.venue} auditorium={t.auditorium} />
    </p>
  )
}

const action = "h-10 border-ink px-4 text-base"

function LetGoRow({ t }: { t: TicketVM }) {
  const [reason, ...allows] = t.notes
  return (
    <li className="grid gap-4 border-b border-ink py-6 md:grid-cols-[1fr_auto] md:items-end md:gap-10">
      <div>
        <Link
          to={t.href}
          className="title text-3xl hover:text-stamp md:text-4xl"
        >
          {t.title}
        </Link>
        <div className="mt-3">
          <When t={t} />
        </div>
        <p className="mt-1 flex gap-4">
          <span>{reason}</span>
          {allows.map((a) => (
            <span key={a} className="text-grain">
              {a}
            </span>
          ))}
        </p>
      </div>
      <div className="flex gap-2">
        {t.onKeep && (
          <Button
            variant="outline"
            aria-pressed={t.keeping}
            onClick={t.onKeep}
            className={cn(
              action,
              t.keeping &&
                "border-stamp bg-stamp text-stamp-ink hover:bg-stamp/85"
            )}
          >
            Keep
          </Button>
        )}
        {t.festivalHref && (
          <ExternalLink
            href={t.festivalHref}
            className={cn(buttonVariants({ variant: "outline" }), action)}
          >
            Festival page
          </ExternalLink>
        )}
        <Button
          onClick={t.onGone}
          disabled={!t.onGone}
          className="h-10 px-5 text-base"
        >
          Gone
        </Button>
      </div>
    </li>
  )
}
