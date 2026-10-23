import type { Icon } from "@phosphor-icons/react"
import { CircleNotchIcon } from "@phosphor-icons/react"
import type { ComponentProps, ReactNode } from "react"
import { Link } from "react-router"

import { Button, buttonVariants } from "@/components/ui/button"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"

/** A link that opens outside the app, in a new tab. */
export function ExternalLink(
  props: Omit<ComponentProps<"a">, "target" | "rel">
) {
  return <a {...props} target="_blank" rel="noreferrer" />
}

/** An icon button, or with `href` an external icon link, that names itself in a tooltip. */
export function Action({
  icon: Glyph,
  label,
  on = false,
  tone = "ink",
  onClick,
  href,
  className,
}: {
  icon: Icon
  label: string
  on?: boolean
  tone?: "ink" | "stamp"
  onClick?: () => void
  href?: string
  className?: string
}) {
  const classes = cn(
    "border-ink bg-transparent disabled:opacity-30 dark:border-ink dark:bg-transparent dark:hover:bg-haze",
    on &&
      tone === "stamp" &&
      "border-stamp bg-stamp text-stamp-ink hover:bg-stamp/85 hover:text-stamp-ink dark:border-stamp dark:bg-stamp dark:hover:bg-stamp/85",
    on &&
      tone === "ink" &&
      "bg-ink text-screen hover:bg-ink/85 hover:text-screen dark:bg-ink dark:hover:bg-ink/85",
    className
  )
  return (
    <Tooltip>
      <TooltipTrigger
        render={
          href ? (
            <ExternalLink
              href={href}
              aria-label={label}
              className={cn(
                buttonVariants({ variant: "outline", size: "icon" }),
                classes
              )}
            />
          ) : (
            <Button
              variant="outline"
              size="icon"
              aria-label={label}
              aria-pressed={on}
              disabled={!onClick}
              onClick={onClick}
              className={classes}
            />
          )
        }
      >
        <Glyph size={18} weight={on ? "bold" : "light"} />
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  )
}

export function NavIcon({
  to,
  icon: Glyph,
  label,
  end,
  count = 0,
  countLabel,
}: {
  to: string
  icon: Icon
  label: string
  end?: boolean
  /** Things to do there; shown as a small ultramarine number. */
  count?: number
  countLabel?: string
}) {
  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <Link
            to={to}
            aria-label={
              count > 0 && countLabel ? `${label}, ${countLabel}` : label
            }
            data-end={end}
            className="flex h-10 items-center gap-2 border-l border-ink px-3 text-sm hover:bg-haze md:px-4"
          />
        }
      >
        <Glyph size={20} weight="light" />
        <span className="hidden md:inline">{label}</span>
        {count > 0 && (
          <span
            aria-hidden
            className="-ml-1 flex h-4 min-w-4 items-center justify-center bg-stamp px-1 text-xs leading-none text-stamp-ink"
          >
            {count}
          </span>
        )}
      </TooltipTrigger>
      <TooltipContent className="md:hidden">{label}</TooltipContent>
    </Tooltip>
  )
}

export function Spinner({ label }: { label: string }) {
  return (
    <span role="status" className="inline-flex items-center gap-2 text-grain">
      <CircleNotchIcon size={18} weight="light" className="animate-spin" />
      <span>{label}</span>
    </span>
  )
}

export function Page({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <main
      className={cn(
        "mx-auto w-full max-w-[90rem] px-4 pb-40 md:px-8",
        className
      )}
    >
      {children}
    </main>
  )
}

export function Loading() {
  return (
    <Page className="py-16">
      <Spinner label="Loading" />
    </Page>
  )
}

export function Missing({
  message,
  href,
  link,
}: {
  message: string
  href?: string
  link?: string
}) {
  return (
    <Page className="py-16">
      <p className="text-xl">{message}</p>
      {href && (
        <Link
          to={href}
          className="mt-4 inline-block underline underline-offset-4"
        >
          {link}
        </Link>
      )}
    </Page>
  )
}

/** Year and country, spaced, never joined by dots. */
export function Meta({
  items,
  className,
}: {
  items: string[]
  className?: string
}) {
  return (
    <p className={cn("flex gap-4 text-grain", className)}>
      {items.map((m) => (
        <span key={m}>{m}</span>
      ))}
    </p>
  )
}
