"""Permission-scoped Source/Idea selection for browser pages and API readers."""

from urllib.parse import urlencode

from django.db import DatabaseError

from .hypothesis_validation import validate_request
from .models import Idea, IdeaVersion, Source, SourceVersion
from .research_context_common import require_actor, visible
from .services import ServiceError


class SelectionUnavailable(ServiceError):
    code = "selection_unavailable"
    safe_message = "Record selection is unavailable."
    http_status = 503


def _selection(*, actor, query, model, version_model, identity_key, route):
    require_actor(actor)
    query = validate_request("SelectionQuery", query)
    # This released slice has shared role access to synthetic identities only.
    # Count and slice the same visibility-filtered queryset; never fall back to
    # unrestricted identities or drop broken versions after counting them.
    qs = visible(model).order_by("-created_at", identity_key)
    page, size = query["page"], query["page_size"]
    start = (page - 1) * size
    try:
        count = qs.count()
        selected = [] if start >= count else qs[start:start + size]
        results = []
        for record in selected:
            if type(record.latest_version) is not int or record.latest_version < 1:
                raise SelectionUnavailable
            fields = ["version", "title", "synthetic"]
            if model is Source:
                fields += ["source", "source_version_id"]
            else:
                fields += ["idea", "idea_version_id", "workflow_status"]
            item = record.versions.only(*fields).get(
                version=record.latest_version, synthetic=True,
            )
            stable_id = getattr(record, identity_key)
            history = f"/{route}/{stable_id}/history"
            result = {
                "stable_id": stable_id, "title": item.title,
                "latest_version": record.latest_version,
                "latest_version_id": item.source_version_id if model is Source else item.idea_version_id,
                "links": {
                    "detail": history if model is Source else f"/ideas/{stable_id}",
                    "history": history,
                    "selected_version": history + f"#{'source' if model is Source else 'idea'}-version-{record.latest_version}",
                },
            }
            if model is Idea:
                result["status"] = item.workflow_status
            results.append(result)
    except (version_model.DoesNotExist, DatabaseError) as error:
        raise SelectionUnavailable from error

    def page_link(number):
        return f"/api/v1/{route}?" + urlencode({"page": number, "page_size": size})

    return {
        "page": page, "page_size": size, "count": count,
        "next": page_link(page + 1) if start + size < count else None,
        "previous": page_link(page - 1) if page > 1 and count else None,
        "results": results,
    }


def list_sources(*, actor, query) -> dict:
    return _selection(actor=actor, query=query, model=Source, version_model=SourceVersion,
                      identity_key="source_id", route="sources")


def list_ideas(*, actor, query) -> dict:
    return _selection(actor=actor, query=query, model=Idea, version_model=IdeaVersion,
                      identity_key="idea_id", route="ideas")
