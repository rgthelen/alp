def register(reg):
    def llm(a, ctx):
        task = a.get("task")
        input_obj = a.get("input") or {}
        schema = a.get("schema")
        provider = a.get("provider")
        model = a.get("model")
        if not task or not schema:
            raise RuntimeError("llm requires 'task' and 'schema'")
        call = ctx.get("call_llm")
        if call is None:
            raise RuntimeError("llm op not available: call_llm missing from context")
        return call(task, input_obj, schema, ctx.get("shapes") or {}, retries=3, provider=provider, model=model)
    reg("llm", llm)
