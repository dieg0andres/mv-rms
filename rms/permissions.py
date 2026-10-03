from rest_framework.permissions import BasePermission, SAFE_METHODS


def _active_authenticated(actor):
    return bool(
        getattr(actor, "is_authenticated", False)
        and getattr(actor, "is_active", False)
    )


def has_rms_read_access(actor) -> bool:
    return bool(
        _active_authenticated(actor)
        and actor.groups.filter(name__in=("editor", "founder_viewer")).exists()
    )


def has_rms_write_access(actor) -> bool:
    return bool(
        _active_authenticated(actor)
        and actor.groups.filter(name="editor").exists()
    )


class IsRmsReader(BasePermission):
    """Authorize the principal before retrieving record data or metadata."""

    def has_permission(self, request, view) -> bool:
        return has_rms_read_access(request.user)


class IsEditor(BasePermission):
    """Allow RMS readers on safe methods and editors on writes."""

    def has_permission(self, request, view) -> bool:
        if request.method in SAFE_METHODS:
            return has_rms_read_access(request.user)
        return has_rms_write_access(request.user)
