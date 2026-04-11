import json


def load_favorites(path):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return []


def save_favorites(path, favorites):
    with open(path, "w") as f:
        json.dump(favorites, f, indent=2)
