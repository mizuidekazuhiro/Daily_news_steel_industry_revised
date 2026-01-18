from src.config.yaml_loader import load_yaml


def _normalize(text):
    return (text or "").lower()


class RuleBasedScorer:
    def __init__(self, rules):
        self.weights = rules.get("weights", {})
        self.keywords = rules.get("keywords", {})
        self.source_trust = rules.get("source_trust", [])
        self.importance = rules.get("importance", {})

    @classmethod
    def from_yaml(cls, path="config/scoring.yml"):
        return cls(load_yaml(path))

    def score(self, article):
        score, _ = self.score_with_reasons(article)
        return score

    def score_with_reasons(self, article):
        text = _normalize(article.get("title", "")) + " " + _normalize(article.get("body", ""))
        score = float(self.weights.get("base", 0))
        reasons = [f"base:{score}"]

        type_key = _normalize(article.get("type", "other"))
        type_weight = float(self.weights.get(type_key, self.weights.get("other", 0)))
        score += type_weight
        reasons.append(f"type:{type_key}({type_weight:+g})")

        high_impact = self.keywords.get("high_impact", [])
        if any(keyword.lower() in text for keyword in high_impact):
            delta = float(self.weights.get("high_impact_keyword", 0))
            score += delta
            reasons.append(f"high_impact_keyword({delta:+g})")

        low_impact = self.keywords.get("low_impact", [])
        if any(keyword.lower() in text for keyword in low_impact):
            delta = float(self.weights.get("low_impact_keyword", 0))
            score += delta
            reasons.append(f"low_impact_keyword({delta:+g})")

        source_text = _normalize(article.get("source", "")) + " " + _normalize(article.get("url", ""))
        for rule in self.source_trust:
            match = _normalize(rule.get("match", ""))
            if match and match in source_text:
                delta = float(rule.get("weight", 0))
                score += delta
                reasons.append(f"source:{match}({delta:+g})")

        return score, reasons

    def importance_label(self, score):
        high = float(self.importance.get("high", 4.0))
        medium = float(self.importance.get("medium", 2.5))
        if score >= high:
            return "High"
        if score >= medium:
            return "Medium"
        return "Low"
