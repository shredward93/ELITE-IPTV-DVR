import json


def load_category_favorites(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return []
        return [str(v) for v in data if str(v).strip()]
    except Exception:
        return []


def save_category_favorites(path, category_ids):
    payload = [str(v) for v in category_ids if str(v).strip()]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
