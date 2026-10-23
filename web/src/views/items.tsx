import type { Icon } from "@phosphor-icons/react"
import {
  ArrowsLeftRightIcon,
  CheckIcon,
  MinusIcon,
  PlusIcon,
  ProhibitIcon,
  TimerIcon,
  WrenchIcon,
  XIcon,
} from "@phosphor-icons/react"

import type { ItemVM } from "@/app/view-models"
import type { ItemVerb } from "@/domain/change-set"

export const verbIcon: Record<ItemVerb, Icon> = {
  commit: PlusIcon,
  release: MinusIcon,
  exclude: ProhibitIcon,
  include: CheckIcon,
  prefer: ArrowsLeftRightIcon,
  buffer: TimerIcon,
  other: WrenchIcon,
}

export function ItemLine({ item }: { item: ItemVM }) {
  const Glyph = verbIcon[item.verb]
  return (
    <li className="flex items-center gap-3 border-b border-haze py-2 last:border-b-0">
      <Glyph
        size={18}
        weight="light"
        aria-label={item.word}
        className="shrink-0"
      />
      <span className="min-w-0 flex-1 truncate">{item.subject}</span>
      {item.onRemove && (
        <button
          type="button"
          onClick={item.onRemove}
          aria-label={`Undo ${item.word.toLowerCase()}`}
          className="flex size-8 items-center justify-center hover:bg-haze"
        >
          <XIcon size={16} weight="light" />
        </button>
      )}
    </li>
  )
}
