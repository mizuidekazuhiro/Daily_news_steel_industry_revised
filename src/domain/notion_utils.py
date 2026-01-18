import hashlib
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode, parse_qs


_TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "gclid",
    "fbclid",
    "yclid",
    "mc_cid",
    "mc_eid",
}


def _expand_google_redirect(url):
    parsed = urlparse(url)
    if parsed.netloc in {"google.com", "www.google.com"} and parsed.path == "/url":
        query = parse_qs(parsed.query)
        if "url" in query:
            return query["url"][0]
        if "q" in query:
            return query["q"][0]
    return url


def normalize_url(url):
    if not url:
        return ""
    expanded = _expand_google_redirect(url)
    parsed = urlparse(expanded)
    query = [(k, v) for k, v in parse_qsl(parsed.query) if k.lower() not in _TRACKING_PARAMS]
    normalized = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower().replace("www.", ""),
        query=urlencode(query, doseq=True),
        fragment="",
    )
    return urlunparse(normalized)


def compute_article_id(url):
    normalized = normalize_url(url)
    if not normalized:
        return ""
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def compute_body_hash(body):
    text = (body or "").strip()
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def split_text_blocks(text, max_len=1800):
    if not text:
        return []
    lines = text.splitlines()
    blocks = []
    current = ""
    for line in lines:
        if len(current) + len(line) + 1 > max_len:
            blocks.append(current)
            current = line
        else:
            current = f"{current}\n{line}".strip()
    if current:
        blocks.append(current)
    return blocks
