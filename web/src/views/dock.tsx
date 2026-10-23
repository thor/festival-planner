// The bottom dock: bars along the bottom edge stack here, above the tray,
// without knowing about each other.

import { createContext, use, type ReactNode } from "react"
import { createPortal } from "react-dom"

export const DockContext = createContext<HTMLElement | null>(null)

/** Render children into the frame's bottom dock. */
export function Docked({ children }: { children: ReactNode }) {
  const dock = use(DockContext)
  return dock ? createPortal(children, dock) : null
}
