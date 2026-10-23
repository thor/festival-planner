import { SignInIcon, UserIcon } from "@phosphor-icons/react"
import type { FormEventHandler } from "react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

import { barCell } from "./parts"

export function AccountView({
  signedIn,
  hint,
  onSubmit,
  onSignOut,
}: {
  signedIn: boolean
  hint: string
  onSubmit: FormEventHandler<HTMLFormElement>
  onSignOut: () => void
}) {
  return (
    <Dialog>
      <DialogTrigger
        aria-label={signedIn ? "Account" : "Sign in"}
        className={barCell}
      >
        {signedIn ? (
          <UserIcon size={20} weight="fill" className="text-stamp" />
        ) : (
          <SignInIcon size={20} weight="light" />
        )}
      </DialogTrigger>
      <DialogContent className="border border-ink bg-screen sm:max-w-md">
        <DialogTitle className="text-lg font-normal">
          {signedIn ? "Signed in" : "Sign in"}
        </DialogTitle>
        {signedIn ? (
          <DialogClose
            render={
              <Button
                variant="outline"
                className="h-10 text-base"
                onClick={onSignOut}
              />
            }
          >
            Sign out
          </DialogClose>
        ) : (
          <form onSubmit={onSubmit} className="flex flex-col gap-3">
            <Label htmlFor="token" className="text-base font-normal">
              Token
            </Label>
            <Input
              id="token"
              name="token"
              type="password"
              autoComplete="off"
              required
              className="h-10 border-ink text-base"
            />
            <p className="text-sm text-grain">{hint}</p>
            <Button type="submit" className="h-10 text-base">
              Sign in
            </Button>
          </form>
        )}
      </DialogContent>
    </Dialog>
  )
}
