def register(reg):
    def filter_nonempty_strings(a, ctx):
        items = a.get("items") or []
        if not isinstance(items, list):
            raise RuntimeError("filter_nonempty_strings expects list 'items'")
        out = []
        for it in items:
            if isinstance(it, str) and it.strip():
                out.append(it.strip())
        return out

    def coalesce_str(a, ctx):
        candidates = []
        if "items" in a and isinstance(a.get("items"), list):
            candidates = a.get("items")
        else:
            candidates = [a.get("a"), a.get("b"), a.get("c"), a.get("d")]
        for v in candidates:
            if isinstance(v, str) and v.strip():
                return v
        return ""

    reg("filter_nonempty_strings", filter_nonempty_strings)
    reg("coalesce_str", coalesce_str)
