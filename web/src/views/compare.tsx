import { Link } from "react-router"

import type { CompareSideVM, CompareVM } from "@/app/view-models"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

import { Meta, Page } from "./parts"

/** Two titles. Tap the one you would rather see. */
export function CompareView({ vm, programmeHref }: { vm: CompareVM; programmeHref: string }) {
  if (!vm.pair) {
    return (
      <Page className="py-16">
        <p className="text-xl">Nothing to compare.</p>
        <Link to={programmeHref} className="mt-4 inline-block underline underline-offset-4">
          Programme
        </Link>
      </Page>
    )
  }
  return (
    <Page className="flex min-h-[calc(100svh-2.5rem)] flex-col">
      <h1 className="sr-only">Which would you rather see?</h1>
      <div className="flex flex-1 flex-col justify-center">
        <Side side={vm.pair.a} state={vm.picked === null ? "idle" : vm.picked === "a" ? "won" : "lost"} />
        <p aria-hidden className="py-4 text-grain">or</p>
        <Side side={vm.pair.b} state={vm.picked === null ? "idle" : vm.picked === "b" ? "won" : "lost"} />
      </div>
      <footer className="flex items-center justify-between border-t border-ink py-4">
        <span className="text-grain">{vm.left} left</span>
        <Button variant="ghost" className="h-10 px-3 text-base" onClick={vm.onSkip} disabled={vm.picked !== null}>
          Skip
        </Button>
      </footer>
    </Page>
  )
}

function Side({ side, state }: { side: CompareSideVM; state: "idle" | "won" | "lost" }) {
  return (
    <button
      type="button"
      onClick={side.onPick}
      disabled={state !== "idle"}
      className={cn(
        "group block w-full border-t border-ink py-6 text-left transition-[color,opacity] duration-400 ease-out",
        state === "won" && "text-stamp",
        state === "lost" && "opacity-20",
      )}
    >
      <span className="title block text-[clamp(3rem,9vw,8rem)] group-hover:text-stamp group-disabled:group-hover:text-inherit">
        {side.title}
      </span>
      <Meta items={side.meta} className="mt-3" />
    </button>
  )
}
