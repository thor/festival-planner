import { CaretUpIcon } from "@phosphor-icons/react"

import type { TrayVM } from "@/app/view-models"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogTitle, DialogTrigger } from "@/components/ui/dialog"

import { ItemLine } from "./items"
import { Spinner } from "./parts"

/** The pending Change Set, in the frame's bottom dock. */
export function TrayView({ vm }: { vm: TrayVM }) {
  if (vm.items.length === 0) return null
  const count = vm.items.length
  return (
    <aside aria-label="Changes" className="border-t border-ink bg-screen">
      <div className="mx-auto flex max-w-[90rem] items-center gap-3 px-4 py-3 md:px-8">
        <Dialog>
          <DialogTrigger render={<Button variant="ghost" className="h-10 gap-2 px-2 text-base" />}>
            <CaretUpIcon size={18} weight="light" />
            {count} {count === 1 ? "change" : "changes"}
          </DialogTrigger>
          <DialogContent className="border border-ink bg-screen sm:max-w-lg">
            <DialogTitle className="text-lg font-normal">Changes</DialogTitle>
            <ul>
              {vm.items.map((item, i) => (
                <ItemLine key={i} item={item} />
              ))}
            </ul>
          </DialogContent>
        </Dialog>

        <span className="min-w-0 flex-1 truncate text-grain">{vm.error ?? vm.items.at(-1)?.subject}</span>

        <Button variant="ghost" className="h-10 px-3 text-base" onClick={vm.onClear}>
          Clear
        </Button>
        {vm.busy ? (
          <Spinner label="Solving" />
        ) : (
          <Button className="h-10 px-5 text-base" disabled={!vm.signedIn} onClick={vm.onSolve}>
            {vm.signedIn ? "Solve" : "Sign in to solve"}
          </Button>
        )}
      </div>
    </aside>
  )
}
