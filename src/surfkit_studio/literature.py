"""Optional literature search (off by default).

The only thing that leaves the computer is the search text the researcher typed: never a dataset,
a result or a session value. The text is checked first (length, no pasted number lists) and the
exact string sent is returned so the app can show it. Results are bibliographic records from
OpenAlex (Crossref as fallback), labelled as unchecked search hits, never as verified citations.

OpenAlex works without a key on a small shared daily budget; a free key can be set in
SURFKIT_OPENALEX_KEY. Crossref needs no key.
"""
from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request

MAX_LEN = 200
MAX_NUMBERS = 4          # more numbers than this looks like pasted data, not a search
TIMEOUT = 20
UA = "SurfactantKit-Studio (literature search; https://github.com/prashant-kotian/SurfactantKit-Studio)"


class QueryRefused(ValueError):
    pass


def check_query(text: str) -> str:
    q = " ".join(str(text or "").split())
    if not q:
        raise QueryRefused("Type what to search for, e.g. 'search: gemini surfactant CMC temperature'.")
    if len(q) > MAX_LEN:
        raise QueryRefused(f"Search text is longer than {MAX_LEN} characters; shorten it to a few keywords.")
    if len(re.findall(r"\d+(?:[.,]\d+)?", q)) > MAX_NUMBERS:
        raise QueryRefused("The search text contains a list of numbers. To keep your data on this computer, "
                           "searches with more than a few numbers are not sent; use keywords instead.")
    return q


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.load(r)


def _openalex(q: str, n: int) -> list[dict]:
    params = {"search": q, "per-page": n,
              "select": "doi,display_name,publication_year,authorships,primary_location"}
    if os.environ.get("SURFKIT_OPENALEX_KEY"):
        params["api_key"] = os.environ["SURFKIT_OPENALEX_KEY"]
    d = _get("https://api.openalex.org/works?" + urllib.parse.urlencode(params))
    out = []
    for w in d.get("results", []):
        src = ((w.get("primary_location") or {}).get("source") or {}).get("display_name")
        out.append({"title": w.get("display_name") or "", "year": w.get("publication_year"),
                    "authors": [a["author"]["display_name"] for a in w.get("authorships", [])[:4]],
                    "more_authors": len(w.get("authorships", [])) > 4, "venue": src or "",
                    "doi": (w.get("doi") or "").replace("https://doi.org/", "")})
    return out


def _crossref(q: str, n: int) -> list[dict]:
    params = {"query": q, "rows": n, "select": "DOI,title,author,issued,container-title"}
    d = _get("https://api.crossref.org/works?" + urllib.parse.urlencode(params))
    out = []
    for w in d.get("message", {}).get("items", []):
        authors = [" ".join(x for x in (a.get("given"), a.get("family")) if x) for a in w.get("author", [])]
        year = (w.get("issued", {}).get("date-parts") or [[None]])[0][0]
        out.append({"title": (w.get("title") or [""])[0], "year": year, "authors": authors[:4],
                    "more_authors": len(authors) > 4, "venue": (w.get("container-title") or [""])[0],
                    "doi": w.get("DOI", "")})
    return out


def search(text: str, n: int = 5) -> dict:
    q = check_query(text)
    errors = []
    for name, fn in (("OpenAlex", _openalex), ("Crossref", _crossref)):
        try:
            return {"query_sent": q, "source": name, "results": fn(q, n)}
        except Exception as e:  # noqa: BLE001 - try the next service, report all failures together
            errors.append(f"{name}: {e}")
    raise ConnectionError("Literature search failed (" + "; ".join(errors) + "). Check the internet connection.")


def as_text(res: dict) -> str:
    lines = [f"Searched {res['source']} for: \"{res['query_sent']}\" (only these words left this computer)."]
    if not res["results"]:
        return lines[0] + "\nNo matching records."
    for i, r in enumerate(res["results"], 1):
        who = ", ".join(r["authors"]) + (" et al." if r["more_authors"] else "")
        bits = [b for b in (who, str(r["year"] or ""), r["venue"]) if b]
        lines.append(f"{i}. {r['title']}. " + "; ".join(bits) + (f". doi:{r['doi']}" if r["doi"] else ""))
    lines.append("These are search hits, not checked citations: read the paper before citing it.")
    return "\n".join(lines)


TRIGGER = re.compile(r"^\s*(search|find papers|find literature|literature)\s*(for|on|about)?\s*[:\-]?\s*", re.I)


def wants_search(message: str) -> str | None:
    """'search: gemini CMC' -> 'gemini CMC'; None when the message is not a search request."""
    m = TRIGGER.match(message)
    return message[m.end():].strip() if m and message[m.end():].strip() else None
