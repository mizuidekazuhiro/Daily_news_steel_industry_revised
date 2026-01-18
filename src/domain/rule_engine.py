from dataclasses import dataclass


def _normalize(text):
    return (text or "").lower()


def _parse_keywords(text):
    return [kw.strip().lower() for kw in (text or "").split(",") if kw.strip()]


@dataclass(frozen=True)
class Rule:
    rule_type: str
    tag_name: str
    keywords: tuple
    negative_keywords: tuple
    match_field: str
    weight: float
    priority: float


def build_rules(raw_rules):
    rules = []
    for entry in raw_rules or []:
        keywords = tuple(_parse_keywords(entry.get("keywords")))
        negative = tuple(_parse_keywords(entry.get("negative_keywords")))
        weight = entry.get("weight")
        priority = entry.get("priority")
        rules.append(Rule(
            rule_type=entry.get("rule_type", "").lower(),
            tag_name=entry.get("tag_name", "").strip(),
            keywords=keywords,
            negative_keywords=negative,
            match_field=entry.get("match_field", "both").lower(),
            weight=float(weight) if weight is not None else 0.0,
            priority=float(priority) if priority is not None else 0.0,
        ))
    return rules


def _match_rule(rule, title_text, body_text):
    if rule.match_field == "title":
        target = title_text
    elif rule.match_field == "body":
        target = body_text
    else:
        target = f"{title_text} {body_text}"

    if not rule.keywords:
        return False

    if not any(keyword in target for keyword in rule.keywords):
        return False

    if rule.negative_keywords and any(kw in target for kw in rule.negative_keywords):
        return False

    return True


def apply_rule_engine(article, rules):
    title_text = _normalize(article.get("title", ""))
    body_text = _normalize(article.get("body_full") or article.get("body") or "")

    country_tags = set()
    sector_tags = set()
    importance_score = 0.0
    importance_reasons = []
    primary_country = None
    primary_priority = float("-inf")

    for rule in rules:
        if not rule.tag_name:
            continue
        if not _match_rule(rule, title_text, body_text):
            continue
        if rule.rule_type == "country":
            country_tags.add(rule.tag_name)
            if rule.priority >= primary_priority:
                primary_priority = rule.priority
                primary_country = rule.tag_name
        elif rule.rule_type == "sector":
            sector_tags.add(rule.tag_name)
        elif rule.rule_type == "importance":
            importance_score += rule.weight
            importance_reasons.append(f"{rule.tag_name}({rule.weight:+g})")

    return {
        "country_tags": sorted(country_tags),
        "sector_tags": sorted(sector_tags),
        "importance_score": importance_score,
        "importance_reasons": importance_reasons,
        "primary_country": primary_country,
    }
