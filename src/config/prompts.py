from src.config.yaml_loader import load_yaml


def load_prompts(path="config/prompts.yml"):
    return load_yaml(path)
