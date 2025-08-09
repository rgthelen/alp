def register(reg):
    def concat(a, ctx):
        items = a.get("items")
        if items is not None:
            return "".join(str(x) for x in items)
        return str(a.get("a", "")) + str(a.get("b", ""))

    def join(a, ctx):
        items = a.get("items") or []
        sep = str(a.get("sep", ""))
        return sep.join(str(x) for x in items)

    def split(a, ctx):
        text = str(a.get("text", ""))
        sep = str(a.get("sep", ","))
        return text.split(sep)

    reg("concat", concat); reg("join", join); reg("split", split)
