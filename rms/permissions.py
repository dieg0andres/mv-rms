from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsEditor(BasePermission):
    """Allow writes only to authenticated members of the editor group."""

    def has_permission(self, request, view) -> bool:
        if request.method in SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.groups.filter(name="editor").exists()
        )
