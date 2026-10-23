import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { BrowserRouter, Route, Routes } from "react-router"

import "./index.css"
import { composePorts } from "@/app/composition"
import { PortsProvider } from "@/app/ports"
import { ThemeProvider } from "@/components/theme-provider"
import { TooltipProvider } from "@/components/ui/tooltip"
import { Compare, DraftPage, Drafts, Film, Frame, Home, Programme, Week } from "@/routes/routes"

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider>
      <PortsProvider ports={composePorts()}>
        <TooltipProvider delay={300}>
          <BrowserRouter>
            <Routes>
              <Route index element={<Home />} />
              <Route path=":slug" element={<Frame />}>
                <Route index element={<Programme />} />
                <Route path="film/:entryId" element={<Film />} />
                <Route path="week" element={<Week />} />
                <Route path="drafts" element={<Drafts />} />
                <Route path="drafts/:draftId" element={<DraftPage />} />
                <Route path="compare" element={<Compare />} />
              </Route>
            </Routes>
          </BrowserRouter>
        </TooltipProvider>
      </PortsProvider>
    </ThemeProvider>
  </StrictMode>,
)
