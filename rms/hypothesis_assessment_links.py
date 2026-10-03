"""Ordered link commitment; FK rows remain the authoritative relationships."""

import hashlib


def assessment_link_seal(links):
    # Internal version IDs are bounded ASCII identifiers. External prose is
    # hashed separately so embedded delimiters/Unicode cannot alter framing.
    lines = []
    for position, link in enumerate(links, 1):
        kind = link["kind"]
        token = (hashlib.sha256(link["reference"].encode("utf-8")).hexdigest()
                 if kind == "external_document" else link["version_id"])
        lines.append(f"{position}:{kind}:{token}\n")
    return {"link_count": len(links),
            "link_digest": hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()}
