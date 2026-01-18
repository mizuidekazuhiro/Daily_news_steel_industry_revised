from src.config.yaml_loader import load_yaml


def load_notion_config(path="config/notion.yml"):
    return load_yaml(path)
