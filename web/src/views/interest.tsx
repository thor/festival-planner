import type { InterestVM } from "@/app/view-models"
import { cn } from "@/lib/utils"

/**
 * Four steps in a row of boxes. A step other than Usual is the User's own,
 * so it takes the stamp; Usual stays quiet.
 */
export function InterestControl({
  vm,
  size = "base",
  className,
}: {
  vm: InterestVM
  /** "sm" sits beside icon actions. */
  size?: "base" | "sm"
  className?: string
}) {
  return (
    <fieldset
      disabled={!vm.onPick}
      className={cn("flex items-center gap-3 disabled:opacity-40", className)}
    >
      <legend className="sr-only">{vm.label}</legend>
      <div className="flex">
        {vm.options.map((o, i) => {
          const on = o.value === vm.value
          const own = on && o.value !== "usual"
          return (
            <label
              key={o.value}
              className={cn(
                "relative flex items-center justify-center border border-ink text-sm text-grain",
                size === "sm" ? "h-8 min-w-14 px-2.5" : "h-10 min-w-15 px-3",
                "has-[:focus-visible]:z-10 has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-stamp",
                "has-[:enabled]:cursor-pointer has-[:enabled]:hover:bg-haze",
                i > 0 && "-ml-px",
                on && "text-ink",
                on && !own && "bg-haze",
                own &&
                  "z-[1] border-stamp bg-stamp text-stamp-ink has-[:enabled]:hover:bg-stamp/85"
              )}
            >
              <input
                type="radio"
                name={vm.label}
                value={o.value}
                checked={on}
                onChange={() => vm.onPick?.(o.value)}
                className="sr-only"
              />
              {o.word}
            </label>
          )
        })}
      </div>
      {vm.pending && (
        <span aria-label="Changed" className="size-1.5 shrink-0 bg-stamp" />
      )}
    </fieldset>
  )
}
