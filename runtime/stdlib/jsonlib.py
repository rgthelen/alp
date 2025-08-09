import json


def register(reg):
    def json_parse(a, ctx):
        text = a.get("text")
        if not isinstance(text, str):
            raise RuntimeError("json_parse requires 'text' string")
        try:
            return json.loads(text)
        except Exception as e:
            raise RuntimeError(f"json_parse failed: {e}")

    def json_get(a, ctx):
        obj = a.get("obj")
        path = a.get("path")
        if not isinstance(path, str) or not path:
            raise RuntimeError("json_get requires 'path'")
        cur = obj
        for part in path.split('.'):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            elif isinstance(cur, list):
                try:
                    idx = int(part)
                except Exception:
                    raise RuntimeError("json_get index must be integer when traversing lists")
                if idx < 0 or idx >= len(cur):
                    raise RuntimeError("json_get index out of range")
                cur = cur[idx]
            else:
                raise RuntimeError("json_get path not found")
        return cur

    reg("json_parse", json_parse); reg("json_get", json_get)
