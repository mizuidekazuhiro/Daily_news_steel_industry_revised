from src.config.yaml_loader import load_yaml


def load_settings(path="config/settings.yml"):
    return load_yaml(path)
