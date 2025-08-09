def register(reg):
    def map_each(a, ctx):
        items = a.get("items") or []
        target_id = a.get("fn")
        if not target_id or target_id not in (ctx.get("fns") or {}):
            raise RuntimeError("map_each requires valid 'fn' id")
        target = ctx["fns"][target_id]
        param = a.get("param")
        results = []
        for it in items:
            inbound_item = {param: it} if param else it
            r, _ = ctx["exec_fn"](target, _inb=inbound_item)
            results.append(r)
        return results

    reg("map_each", map_each)
