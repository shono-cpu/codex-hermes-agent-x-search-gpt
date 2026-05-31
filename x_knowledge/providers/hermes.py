from __future__ import annotations

from ..models import ContentInput


class HermesXSearchProvider:
    """Adapter boundary for Codex -> Hermes Agent -> x_search.

    This class is intentionally small: once the Hermes Agent invocation is stable
    in Codex, implement fetch_posts() so the rest of the pipeline can stay fixed.
    """

    def fetch_posts(self, account: str, limit: int = 30) -> list[ContentInput]:
        raise NotImplementedError(
            "Hermes Agent is not exposed in this Codex session yet. "
            "Implement this method with the stable x_search call shape."
        )
