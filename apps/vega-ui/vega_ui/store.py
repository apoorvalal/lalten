"""In-memory session store for chart editing sessions."""

from __future__ import annotations

import copy
import uuid
from typing import Any

from vega_ui.models.chart import ChartSession


class SessionNotFoundError(Exception):
    """Raised when a session ID is not found."""


class NothingToUndoError(Exception):
    """Raised when undo is called with empty history."""


class SessionStore:
    """Thread-safe in-memory store for chart sessions.

    Suitable for single-process development. Not intended for production
    multi-process deployments.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, ChartSession] = {}

    def create(self, spec: dict[str, Any]) -> ChartSession:
        """Create a new session with the given annotated spec."""
        session_id = str(uuid.uuid4())[:12]
        session = ChartSession(
            id=session_id,
            spec=copy.deepcopy(spec),
            original_spec=copy.deepcopy(spec),
            history=[],
        )
        self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> ChartSession:
        """Retrieve a session by ID."""
        session = self._sessions.get(session_id)
        if session is None:
            raise SessionNotFoundError(f"Session '{session_id}' not found")
        return session

    def update_spec(self, session_id: str, new_spec: dict[str, Any]) -> ChartSession:
        """Update the spec for a session, pushing current to history."""
        session = self.get(session_id)
        session.history.append(copy.deepcopy(session.spec))
        session.spec = copy.deepcopy(new_spec)
        return session

    def undo(self, session_id: str) -> ChartSession:
        """Revert to the previous spec in history."""
        session = self.get(session_id)
        if not session.history:
            raise NothingToUndoError("No history to undo")
        session.spec = session.history.pop()
        return session

    def delete(self, session_id: str) -> None:
        """Remove a session."""
        if session_id not in self._sessions:
            raise SessionNotFoundError(f"Session '{session_id}' not found")
        del self._sessions[session_id]

    def list_sessions(self) -> list[str]:
        """Return all active session IDs."""
        return list(self._sessions.keys())
