from src.config.yaml_loader import load_yaml
from src.domain.rule_engine import apply_rule_engine, build_rules


def _normalize(text):
    return (text or "").lower()


def _match_keywords(text, mapping):
    hits = set()
    for key, keywords in mapping.items():
        for kw in keywords or []:
            if _normalize(kw) in text:
                hits.add(key)
                break
    return sorted(hits)


def load_tag_rules(path="config/tagging.yml"):
    return load_yaml(path)


def apply_tags(article, rules=None, notion_rules=None):
    if notion_rules:
        engine_rules = build_rules(notion_rules)
        result = apply_rule_engine(article, engine_rules)
        article["country_tags"] = result["country_tags"]
        article["sector_tags"] = result["sector_tags"]
        article["primary_country"] = result["primary_country"]
        return article

    rules = rules or load_tag_rules()
    text = _normalize(article.get("title", "")) + " " + _normalize(article.get("body_full", "")) + " " + _normalize(article.get("body", ""))
    countries = _match_keywords(text, rules.get("countries", {}))
    sectors = _match_keywords(text, rules.get("sectors", {}))
    article["country_tags"] = countries
    article["sector_tags"] = sectors
    return article
