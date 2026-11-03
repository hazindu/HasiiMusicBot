class TrackChangedError(RuntimeError):
    """The track associated with a requester control is no longer current."""


def ensure_current_track(current, expected) -> None:
    if expected is not None and current is not expected:
        raise TrackChangedError("The current track changed")
