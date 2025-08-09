def register(reg):
    def add(a, ctx):
        return (a.get("a", 0) or 0) + (a.get("b", 0) or 0)
    def sub(a, ctx):
        return (a.get("a", 0) or 0) - (a.get("b", 0) or 0)
    def mul(a, ctx):
        return (a.get("a", 0) or 0) * (a.get("b", 0) or 0)
    def div(a, ctx):
        b = (a.get("b", 0) or 0)
        if b == 0:
            raise ZeroDivisionError("Division by zero in div op")
        return (a.get("a", 0) or 0) / b
    def pow_(a, ctx):
        return (a.get("a", 0) or 0) ** (a.get("b", 0) or 0)
    def neg(a, ctx):
        return - (a.get("x", 0) or 0)
    def min_(a, ctx):
        items = a.get("items")
        if isinstance(items, list):
            return min(items) if items else 0
        return min(a.get("a", 0), a.get("b", 0))
    def max_(a, ctx):
        items = a.get("items")
        if isinstance(items, list):
            return max(items) if items else 0
        return max(a.get("a", 0), a.get("b", 0))
    def abs_(a, ctx):
        return abs(a.get("x", 0))
    def round_(a, ctx):
        x = a.get("x", 0)
        nd = a.get("ndigits")
        return round(x, int(nd)) if nd is not None else round(x)

    def calc_eval(a, ctx):
        expr = a.get("expr")
        if isinstance(expr, dict) and "expr" in expr:
            expr = expr.get("expr")
        return {"value": _safe_eval_expr(expr)}

    import ast, operator as op
    def _safe_eval_expr(expr: str) -> float:
        if not isinstance(expr, str):
            raise TypeError("expr must be a string")
        expr_py = expr.replace("^", "**")
        allowed_binops = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv, ast.FloorDiv: op.floordiv, ast.Mod: op.mod, ast.Pow: op.pow}
        allowed_unaryops = {ast.UAdd: op.pos, ast.USub: op.neg}
        def eval_node(n):
            if isinstance(n, ast.Expression): return eval_node(n.body)
            if isinstance(n, ast.Num): return float(n.n)
            if isinstance(n, ast.Constant) and isinstance(n.value, (int,float)): return float(n.value)
            if isinstance(n, ast.BinOp) and type(n.op) in allowed_binops:
                return allowed_binops[type(n.op)](eval_node(n.left), eval_node(n.right))
            if isinstance(n, ast.UnaryOp) and type(n.op) in allowed_unaryops:
                return allowed_unaryops[type(n.op)](eval_node(n.operand))
            raise ValueError("Unsupported expression element")
        return float(eval_node(ast.parse(expr_py, mode="eval")))

    def to_calc_result(a, ctx):
        return {"value": float(a.get("value", 0))}

    reg("add", add); reg("sub", sub); reg("mul", mul); reg("div", div); reg("pow", pow_); reg("neg", neg)
    reg("min", min_); reg("max", max_); reg("abs", abs_); reg("round", round_)
    reg("calc_eval", calc_eval); reg("to_calc_result", to_calc_result)
