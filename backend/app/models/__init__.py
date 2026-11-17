"""Import all models so Base.metadata is fully populated."""

from app.models import (  # noqa: F401
    ai,
    collaboration,
    common,
    family,
    identity,
    legacy,
    legacy_tables,
    media,
    memory,
    publishing,
    story,
)
