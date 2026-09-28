"""Request-scoped dependencies shared by the routers."""

from __future__ import annotations

from fastapi import HTTPException, Request

from control_plane.store.runs import RunRepository


def runs_repo(request: Request) -> RunRepository:
    """The run repository, or a 503 that names the missing variable.

    A fresh clone has no DATABASE_URL. Every portal route answers the same way in
    that state, so nobody debugs a blank screen: the response says what to set.
    """
    repo = getattr(request.app.state, "runs", None)
    if repo is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "DATABASE_URL is not set; the control plane has no database to read runs from"
            ),
        )
    return repo
