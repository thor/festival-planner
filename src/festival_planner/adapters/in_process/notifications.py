"""DraftSolvedNotifier adapters for a single process."""

from ...domain.drafts import Draft


class NullDraftSolvedNotifier:
    """Nobody is listening yet; clients poll."""

    def draft_solved(self, draft: Draft) -> None:
        pass
