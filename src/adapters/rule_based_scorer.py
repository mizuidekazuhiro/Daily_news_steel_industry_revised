from src.config.yaml_loader import load_yaml


def _normalize(text):
    return (text or "").lower()


class RuleBasedScorer:
    def __init__(self, rules):
        self.weights = rules.get("weights", {})
        self.keywords = rules.get("keywords", {})
        self.source_trust = rules.get("source_trust", [])

    @classmethod
    def from_yaml(cls, path="config/scoring.yml"):
        return cls(load_yaml(path))

    def score(self, article):
        text = _normalize(article.get("title", "")) + " " + _normalize(article.get("body", ""))
        score = float(self.weights.get("base", 0))

        type_key = _normalize(article.get("type", "other"))
        score += float(self.weights.get(type_key, self.weights.get("other", 0)))

        high_impact = self.keywords.get("high_impact", [])
        if any(keyword.lower() in text for keyword in high_impact):
            score += float(self.weights.get("high_impact_keyword", 0))

        low_impact = self.keywords.get("low_impact", [])
        if any(keyword.lower() in text for keyword in low_impact):
            score += float(self.weights.get("low_impact_keyword", 0))

        source_text = _normalize(article.get("source", "")) + " " + _normalize(article.get("url", ""))
        for rule in self.source_trust:
            match = _normalize(rule.get("match", ""))
            if match and match in source_text:
                score += float(rule.get("weight", 0))

        return score
