import difflib
import re
import unicodedata
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_QUERY_PREFIXES = ("utm_",)
TRACKING_QUERY_KEYS = {"fbclid", "gclid", "igshid", "mc_cid", "mc_eid"}
TITLE_SUFFIX_PATTERN = re.compile(r"\s*(?:[-|｜]\s*(?:reuters|ロイター|bloomberg|ブルームバーグ|鉄鋼新聞))\s*$", re.IGNORECASE)
NON_WORD_PATTERN = re.compile(r"[^\w\s]")
WHITESPACE_PATTERN = re.compile(r"\s+")


def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_dt_value(value):
    if isinstance(value, datetime):
        return value.timestamp()
    return float("-inf")


def normalize_url(url):
    if not url:
        return ""

    split = urlsplit(str(url).strip())
    scheme = (split.scheme or "https").lower()
    netloc = split.netloc.lower()
    path = split.path.rstrip("/") or "/"

    filtered_query = []
    for key, val in parse_qsl(split.query, keep_blank_values=True):
        lower_key = key.lower()
        if lower_key.startswith(TRACKING_QUERY_PREFIXES):
            continue
        if lower_key in TRACKING_QUERY_KEYS:
            continue
        filtered_query.append((lower_key, val))
    filtered_query.sort()
    query = urlencode(filtered_query)

    return urlunsplit((scheme, netloc, path, query, ""))


def normalize_text(text):
    normalized = unicodedata.normalize("NFKC", str(text or "")).lower()
    normalized = NON_WORD_PATTERN.sub(" ", normalized)
    normalized = WHITESPACE_PATTERN.sub(" ", normalized).strip()
    return normalized


def normalize_title_for_dedup(title):
    normalized = unicodedata.normalize("NFKC", str(title or "")).strip().lower()
    normalized = TITLE_SUFFIX_PATTERN.sub("", normalized)
    normalized = NON_WORD_PATTERN.sub(" ", normalized)
    normalized = WHITESPACE_PATTERN.sub(" ", normalized).strip()
    return normalized


def normalize_body_for_dedup(body):
    return normalize_text(body)


def body_similarity(article_a, article_b, *, compare_chars=1200):
    body_a = normalize_body_for_dedup(article_a.get("body_full") or article_a.get("body") or "")
    body_b = normalize_body_for_dedup(article_b.get("body_full") or article_b.get("body") or "")
    if len(body_a) < 300 or len(body_b) < 300:
        return 0.0
    return difflib.SequenceMatcher(None, body_a[:compare_chars], body_b[:compare_chars]).ratio()


def is_same_day(article_a, article_b):
    dt_a = article_a.get("final_dt")
    dt_b = article_b.get("final_dt")
    if not isinstance(dt_a, datetime) or not isinstance(dt_b, datetime):
        return False
    return dt_a.date() == dt_b.date()


def choose_best_article(articles):
    def rank(article):
        importance = safe_float(article.get("importance_score"), safe_float(article.get("score"), 0.0))
        score = safe_float(article.get("score"), 0.0)
        dt_value = safe_dt_value(article.get("final_dt"))
        body_len = len(article.get("body_full") or article.get("body") or "")
        title_len = len(article.get("title") or "")
        url_len = len(article.get("url") or "")
        return (importance, score, dt_value, body_len, title_len, -url_len)

    return max(articles, key=rank)


def deduplicate_articles(articles, *, similarity_threshold=0.92):
    if not articles:
        return [], {
            "before_dedup_count": 0,
            "after_dedup_count": 0,
            "removed_by_normalized_url": 0,
            "removed_by_normalized_title": 0,
            "removed_by_body_similarity": 0,
            "merge_details": [],
        }

    duplicates = {}
    reason_by_removed = {}

    # Stage 1: normalized URL duplicates.
    by_url = {}
    for idx, article in enumerate(articles):
        norm_url = normalize_url(article.get("url"))
        if norm_url and norm_url in by_url:
            duplicates[idx] = by_url[norm_url]
            reason_by_removed[idx] = "url"
        else:
            by_url[norm_url] = idx

    # Stage 2 and 3 on URL-unique articles.
    candidate_indexes = [idx for idx in range(len(articles)) if idx not in duplicates]
    for pos, idx in enumerate(candidate_indexes):
        if idx in duplicates:
            continue
        base = articles[idx]
        base_title = normalize_title_for_dedup(base.get("title"))
        for other_idx in candidate_indexes[pos + 1:]:
            if other_idx in duplicates:
                continue
            other = articles[other_idx]
            other_title = normalize_title_for_dedup(other.get("title"))

            title_duplicate = False
            if base_title and base_title == other_title:
                similarity = body_similarity(base, other)
                if is_same_day(base, other) or similarity >= similarity_threshold:
                    title_duplicate = True

            if title_duplicate:
                duplicates[other_idx] = idx
                reason_by_removed[other_idx] = "title"
                continue

            similarity = body_similarity(base, other)
            if similarity >= similarity_threshold:
                duplicates[other_idx] = idx
                reason_by_removed[other_idx] = "body_similarity"

    groups = {}
    for idx in range(len(articles)):
        root = idx
        while root in duplicates:
            root = duplicates[root]
        groups.setdefault(root, []).append(idx)

    deduped = []
    merge_details = []
    removed_url = 0
    removed_title = 0
    removed_body = 0

    for indexes in groups.values():
        group_articles = [articles[i] for i in indexes]
        best = choose_best_article(group_articles)
        best_idx = indexes[group_articles.index(best)]
        deduped.append(best)

        for idx in indexes:
            if idx == best_idx:
                continue
            reason = reason_by_removed.get(idx, "url")
            if reason == "url":
                removed_url += 1
            elif reason == "title":
                removed_title += 1
            elif reason == "body_similarity":
                removed_body += 1
            merge_details.append(
                {
                    "removed_title": articles[idx].get("title", ""),
                    "kept_title": best.get("title", ""),
                    "reason": reason,
                }
            )

    stats = {
        "before_dedup_count": len(articles),
        "after_dedup_count": len(deduped),
        "removed_by_normalized_url": removed_url,
        "removed_by_normalized_title": removed_title,
        "removed_by_body_similarity": removed_body,
        "merge_details": merge_details,
    }
    return deduped, stats


def filter_negative_importance_articles(articles):
    kept = []
    removed = []
    for article in articles:
        score = article.get("importance_score")
        if score is None:
            score = article.get("score")
        value = safe_float(score, 0.0)
        if value < 0:
            removed.append(article)
        else:
            kept.append(article)
    return kept, removed
