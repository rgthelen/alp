# alp_vm.py — neural-symbolic VM stub with real LLM adapters
import json
import hashlib
import time
import sys
import os
import urllib.request
import urllib.parse
import ipaddress

# Optional providers — imported lazily inside call sites to avoid import-time errors

def load_graph(path):
    shapes, fns, flow = {}, {}, []
    with open(path) as f:
        for line in f:
            if not line.strip():
                continue
            n = json.loads(line)
            if n["kind"] == "@shape":
                # store full shape def for defaults/enums/metadata
                shape_def = {
                    "fields": n.get("fields", {}),
                }
                if "defaults" in n:
                    shape_def["defaults"] = n["defaults"]
                if "doc" in n:
                    shape_def["doc"] = n["doc"]
                shapes[n["id"]] = shape_def
            elif n["kind"] == "@fn":
                fns[n["id"]] = n
            elif n["kind"] == "@flow":
                flow.extend(n.get("edges", []))
    return shapes, fns, flow

def hash_obj(o): return "h:" + hashlib.sha256(json.dumps(o, sort_keys=True).encode()).hexdigest()[:8]

def resolve_args(args, env):
    """Resolve op arguments with env, supporting dotted paths like $input.expr, recursively."""
    def get_from_env(path_str):
        key = path_str[1:]  # strip leading $
        parts = key.split(".") if "." in key else [key]
        cur = env
        for part in parts:
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return env.get(key)
        return cur

    def resolve_value(v):
        if isinstance(v, str) and v.startswith("$"):
            return get_from_env(v)
        if isinstance(v, list):
            return [resolve_value(x) for x in v]
        if isinstance(v, dict):
            return {kk: resolve_value(vv) for kk, vv in v.items()}
        return v

    return {k: resolve_value(v) for k, v in (args or {}).items()}

# ---------------- Schema + Provider helpers ----------------
def _get_shape_def(shape_name, shapes):
    raw = shapes.get(shape_name, {})
    if isinstance(raw, dict) and "fields" in raw:
        return raw
    # backward-compat: shapes stored as fields dict
    if isinstance(raw, dict):
        return {"fields": raw}
    return {"fields": {}}

def shape_to_json_schema(shape_name, shapes):
    """Convert a simple @shape into a JSON Schema v7-ish dict."""
    shape_def = _get_shape_def(shape_name, shapes)
    fields = shape_def.get("fields", {})
    props = {}
    required = []
    type_map = {"str":"string","int":"number","float":"number","bool":"boolean","ts":"string"}
    for k, v in fields.items():
        opt = k.endswith("?")
        key = k[:-1] if opt else k
        if not opt:
            required.append(key)
        # Support list<T>, list, map<T>, map
        if isinstance(v, str) and v.startswith("enum<") and v.endswith(">"):
            vals = [x.strip() for x in v[5:-1].split(",") if x.strip()]
            props[key] = {"enum": vals}
        elif isinstance(v, str) and v.startswith("list"):
            item_type = None
            if "<" in v and v.endswith(">"):
                item_type = v[v.find("<")+1:-1]
            item_schema = {"type": type_map.get(item_type, "number" if item_type in ("int","float") else "string")} if item_type else {}
            props[key] = {"type": "array", "items": item_schema} if item_schema else {"type": "array"}
        elif isinstance(v, str) and v.startswith("map"):
            val_type = None
            if "<" in v and v.endswith(">"):
                val_type = v[v.find("<")+1:-1]
            additional = {"type": type_map.get(val_type, "number" if val_type in ("int","float") else "string")} if val_type else {}
            props[key] = {"type": "object", "additionalProperties": additional} if additional else {"type": "object"}
        else:
            props[key] = {"type": type_map.get(v, "object")}
        if v == "ts":
            props[key]["format"] = "date-time"
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": shape_name,
        "type": "object",
        "properties": props,
        "required": required,
        "additionalProperties": False
    }

def _apply_shape_defaults(obj, shape_name, shapes):
    shape_def = _get_shape_def(shape_name, shapes)
    defaults = shape_def.get("defaults") or {}
    if not defaults:
        return obj
    out = dict(obj)
    for k, v in defaults.items():
        if k not in out:
            out[k] = v
    return out

def validate_against_shape(obj, shape_name, shapes):
    """Strict validation against the declared @shape without external deps."""
    shape_def = _get_shape_def(shape_name, shapes)
    fields = shape_def.get("fields", {})
    if not isinstance(obj, dict):
        raise AssertionError("Result is not an object")
    # required keys
    for k in fields.keys():
        opt = k.endswith("?")
        key = k[:-1] if opt else k
        if not opt and key not in obj:
            raise AssertionError(f"Schema mismatch, missing: {key}")
    # no extra keys
    base_keys = { (k[:-1] if k.endswith("?") else k) for k in fields.keys() }
    extras = [k for k in obj.keys() if k not in base_keys]
    if extras:
        raise AssertionError(f"Schema mismatch, extra keys: {extras}")
    # type checks (lightweight)
    for k, t in fields.items():
        opt = k.endswith("?")
        key = k[:-1] if opt else k
        if key not in obj:
            continue
        v = obj[key]
        if isinstance(t, str) and t.startswith("enum<") and t.endswith(">"):
            vals = [x.strip() for x in t[5:-1].split(",") if x.strip()]
            if v not in vals:
                raise AssertionError(f"Field '{key}' not in enum {vals}")
            continue
        if t == "str" and not isinstance(v, str):
            raise AssertionError(f"Field '{key}' not str")
        if t in ("int", "float") and not isinstance(v, (int, float)):
            raise AssertionError(f"Field '{key}' not number")
        if t == "bool" and not isinstance(v, bool):
            raise AssertionError(f"Field '{key}' not bool")
        # lists
        if isinstance(t, str) and t.startswith("list"):
            if not isinstance(v, list):
                raise AssertionError(f"Field '{key}' not list")
            if "<" in t and t.endswith(">"):
                elem_t = t[t.find("<")+1:-1]
                for idx, item in enumerate(v):
                    if elem_t in ("int","float") and not isinstance(item, (int,float)):
                        raise AssertionError(f"Field '{key}[{idx}]' not number")
                    if elem_t == "str" and not isinstance(item, str):
                        raise AssertionError(f"Field '{key}[{idx}]' not str")
                    if elem_t == "bool" and not isinstance(item, bool):
                        raise AssertionError(f"Field '{key}[{idx}]' not bool")
        # maps
        if isinstance(t, str) and t.startswith("map"):
            if not isinstance(v, dict):
                raise AssertionError(f"Field '{key}' not map/object")
            if "<" in t and t.endswith(">"):
                val_t = t[t.find("<")+1:-1]
                for kk2, vv2 in v.items():
                    if val_t in ("int","float") and not isinstance(vv2, (int,float)):
                        raise AssertionError(f"Field '{key}.{kk2}' not number")
                    if val_t == "str" and not isinstance(vv2, str):
                        raise AssertionError(f"Field '{key}.{kk2}' not str")
                    if val_t == "bool" and not isinstance(vv2, bool):
                        raise AssertionError(f"Field '{key}.{kk2}' not bool")
    return True

def get_provider():
    provider = (os.getenv("ALP_MODEL_PROVIDER") or "mock").lower()
    model = os.getenv("ALP_MODEL_NAME")
    # defaults
    if provider == "openai" and not model:
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    if provider == "anthropic" and not model:
        model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20240620")
    return provider, model

def op_add(args):
    return (args.get("a", 0) or 0) + (args.get("b", 0) or 0)

def op_sub(args):
    return (args.get("a", 0) or 0) - (args.get("b", 0) or 0)

def op_mul(args):
    return (args.get("a", 0) or 0) * (args.get("b", 0) or 0)

def op_div(args):
    b = (args.get("b", 0) or 0)
    if b == 0:
        raise ZeroDivisionError("Division by zero in div op")
    return (args.get("a", 0) or 0) / b

def op_pow(args):
    return (args.get("a", 0) or 0) ** (args.get("b", 0) or 0)

def op_neg(args):
    return - (args.get("x", 0) or 0)

def op_min(args):
    if "items" in args and isinstance(args["items"], list):
        return min(args["items"]) if args["items"] else 0
    return min(args.get("a", 0), args.get("b", 0))

def op_max(args):
    if "items" in args and isinstance(args["items"], list):
        return max(args["items"]) if args["items"] else 0
    return max(args.get("a", 0), args.get("b", 0))

def op_abs(args):
    return abs(args.get("x", 0))

def op_round(args):
    x = args.get("x", 0)
    nd = args.get("ndigits")
    try:
        return round(x, int(nd)) if nd is not None else round(x)
    except Exception:
        return round(float(x))

def op_sum(args):
    items = args.get("items") or []
    if not isinstance(items, list):
        raise RuntimeError("sum expects list 'items'")
    total = 0.0
    for it in items:
        total += float(it)
    return total

def op_avg(args):
    items = args.get("items") or []
    if not isinstance(items, list):
        raise RuntimeError("avg expects list 'items'")
    if not items:
        return 0.0
    return op_sum({"items": items}) / len(items)

def _safe_eval_expr(expr: str) -> float:
    """Safely evaluate a basic arithmetic expression.

    Supported: +, -, *, /, //, %, **, parentheses, unary +/-, and numbers.
    Also supports caret (^) as exponent by translating to **.
    """
    import ast
    import operator as op

    if not isinstance(expr, str):
        raise TypeError("expr must be a string")

    # translate caret to exponent
    expr_py = expr.replace("^", "**")

    allowed_binops = {
        ast.Add: op.add,
        ast.Sub: op.sub,
        ast.Mult: op.mul,
        ast.Div: op.truediv,
        ast.FloorDiv: op.floordiv,
        ast.Mod: op.mod,
        ast.Pow: op.pow,
    }
    allowed_unaryops = {
        ast.UAdd: op.pos,
        ast.USub: op.neg,
    }

    def eval_node(n):
        if isinstance(n, ast.Expression):
            return eval_node(n.body)
        if isinstance(n, ast.Num):  # Py<3.8
            return float(n.n)
        if isinstance(n, ast.Constant):  # Py>=3.8
            if isinstance(n.value, (int, float)):
                return float(n.value)
            raise ValueError("Only numeric constants allowed")
        if isinstance(n, ast.BinOp):
            if type(n.op) not in allowed_binops:
                raise ValueError("Operator not allowed")
            left = eval_node(n.left)
            right = eval_node(n.right)
            func = allowed_binops[type(n.op)]
            return func(left, right)
        if isinstance(n, ast.UnaryOp):
            if type(n.op) not in allowed_unaryops:
                raise ValueError("Unary operator not allowed")
            operand = eval_node(n.operand)
            func = allowed_unaryops[type(n.op)]
            return func(operand)
        raise ValueError("Unsupported expression element")

    tree = ast.parse(expr_py, mode="eval")
    return float(eval_node(tree))

def op_calc_eval(args):
    expr = args.get("expr")
    if isinstance(expr, dict) and "expr" in expr:
        expr = expr.get("expr")
    value = _safe_eval_expr(expr)
    return {"value": value}

def op_to_calc_result(args):
    return {"value": float(args.get("value", 0))}

def op_json_parse(args):
    text = args.get("text")
    if not isinstance(text, str):
        raise RuntimeError("json_parse requires 'text' string")
    try:
        obj = json.loads(text)
    except Exception as e:
        raise RuntimeError(f"json_parse failed: {e}")
    return obj

def op_json_get(args):
    obj = args.get("obj")
    path = args.get("path")
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

def _io_root() -> str:
    return os.getenv("ALP_IO_ROOT", os.getcwd())

def _io_allow_write() -> bool:
    return os.getenv("ALP_IO_ALLOW_WRITE", "0") in ("1", "true", "yes")

def _safe_path_join(root: str, path: str) -> str:
    base = os.path.abspath(root)
    target = os.path.abspath(os.path.join(base, path))
    if not target.startswith(base + os.sep) and target != base:
        raise RuntimeError("Path escapes IO root")
    return target

def op_read_file(args):
    path = args.get("path")
    if not isinstance(path, str) or not path:
        raise RuntimeError("read_file requires 'path'")
    root = _io_root()
    abs_path = _safe_path_join(root, path)
    encoding = args.get("encoding") or "utf-8"
    with open(abs_path, "r", encoding=encoding) as f:
        text = f.read()
    return {"text": text}

def op_write_file(args):
    if not _io_allow_write():
        raise RuntimeError("Writes disabled. Set ALP_IO_ALLOW_WRITE=1 to enable.")
    path = args.get("path")
    text = args.get("text", "")
    if not isinstance(path, str) or not path:
        raise RuntimeError("write_file requires 'path'")
    root = _io_root()
    abs_path = _safe_path_join(root, path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    encoding = args.get("encoding") or "utf-8"
    mode = "a" if args.get("append") else "w"
    with open(abs_path, mode, encoding=encoding) as f:
        f.write(str(text))
    return {"ok": True}

def _http_is_private_host(host: str) -> bool:
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_private or ip.is_loopback or ip.is_link_local
    except ValueError:
        # not an IP literal
        return host in ("localhost",)

def _http_allowed(url: str) -> bool:
    parts = urllib.parse.urlsplit(url)
    host = parts.hostname or ""
    if not host:
        return False
    # block local unless explicitly disabled
    block_local = os.getenv("ALP_HTTP_BLOCK_LOCAL", "1") != "0"
    if block_local and _http_is_private_host(host):
        return False
    allowlist = os.getenv("ALP_HTTP_ALLOWLIST", "").strip()
    if not allowlist:
        return False
    allowed_hosts = {h.strip().lower() for h in allowlist.split(",") if h.strip()}
    return host.lower() in allowed_hosts

def _http_fetch(method: str, url: str, data_bytes: bytes | None, headers: dict | None):
    if not _http_allowed(url):
        raise RuntimeError("HTTP blocked by allowlist. Set ALP_HTTP_ALLOWLIST=host1,host2")
    timeout = float(os.getenv("ALP_HTTP_TIMEOUT", "10"))
    req = urllib.request.Request(url=url, method=method)
    for k, v in (headers or {}).items():
        req.add_header(str(k), str(v))
    max_bytes = int(os.getenv("ALP_HTTP_MAX_BYTES", "1000000"))
    with urllib.request.urlopen(req, data=data_bytes, timeout=timeout) as resp:
        status = getattr(resp, "status", 200)
        body = resp.read(max_bytes)
    try:
        text = body.decode("utf-8", errors="replace")
    except Exception:
        text = ""
    return {"status": int(status), "text": text}

def op_http(args):
    method = str(args.get("method") or "GET").upper()
    url = args.get("url")
    if not isinstance(url, str) or not url:
        raise RuntimeError("http requires 'url'")
    headers = args.get("headers") if isinstance(args.get("headers"), dict) else None
    data_bytes = None
    if "json" in args and args.get("json") is not None:
        payload = json.dumps(args.get("json")).encode("utf-8")
        headers = headers or {}
        headers.setdefault("Content-Type", "application/json")
        data_bytes = payload
    elif "data" in args and args.get("data") is not None:
        data_bytes = (str(args.get("data"))).encode("utf-8")
    return _http_fetch(method, url, data_bytes, headers)


def _openai_call(task, input_obj, schema_dict, model):
    try:
        import openai  # type: ignore
    except Exception:
        raise RuntimeError("OpenAI SDK not installed. pip install openai")
    client = openai.OpenAI()
    # Try JSON schema mode if available; fallback to instructions.
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role":"system","content":"You are a JSON generator. Output ONLY JSON that strictly matches the provided JSON Schema."},
                {"role":"user","content":json.dumps({
                    "task": task,
                    "input": input_obj,
                    "json_schema": schema_dict
                })}
            ],
            temperature=0.2,
        )
        text = resp.choices[0].message["content"]
    except Exception:
        # New Responses API or schema modes vary; fallback minimal prompt
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role":"system","content":"Return ONLY JSON. No prose."},
                {"role":"user","content":f"Task: {task}\nInput: {json.dumps(input_obj)}\nSchema Title: {schema_dict.get('title')}\nRespond with JSON only."}
            ],
            temperature=0.2,
        )
        text = resp.choices[0].message["content"]
    try:
        return json.loads(text)
    except Exception as e:
        raise AssertionError(f"Model did not return JSON: {e}")

def _anthropic_call(task, input_obj, schema_dict, model):
    try:
        import anthropic  # type: ignore
    except Exception:
        raise RuntimeError("Anthropic SDK not installed. pip install anthropic")
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=model,
        max_tokens=512,
        temperature=0.2,
        system="Return ONLY JSON matching the provided JSON structure. No explanations.",
        messages=[{
            "role":"user",
            "content": [
                {"type":"text","text":
                    "Task: " + task + "\n" +
                    "Input: " + json.dumps(input_obj) + "\n" +
                    "Schema Title: " + (schema_dict.get("title") or "") + "\n" +
                    "Respond with JSON only."}
            ]
        }]
    )
    # Anthropic SDK returns content blocks
    parts = []
    for b in msg.content:
        if hasattr(b, "type") and b.type == "text" and hasattr(b, "text"):
            parts.append(b.text)
        elif isinstance(b, dict) and b.get("type") == "text":
            parts.append(b.get("text", ""))
    text = "".join(parts)
    try:
        return json.loads(text)
    except Exception as e:
        raise AssertionError(f"Model did not return JSON: {e}")

def call_llm(task, input_obj, schema_name, shapes, retries=3):
    provider, model = get_provider()
    schema_dict = shape_to_json_schema(schema_name, shapes)
    last_err = None
    for attempt in range(1, (retries or 1) + 1):
        try:
            if provider == "openai":
                cand = _openai_call(task, input_obj, schema_dict, model)
            elif provider == "anthropic":
                cand = _anthropic_call(task, input_obj, schema_dict, model)
            else:
                # mock provider — synthesize a valid object from schema types
                props = schema_dict.get("properties", {})
                def _default_for(prop):
                    t = (prop or {}).get("type")
                    if t == "string":
                        # Prefer any obvious input text
                        base = input_obj.get("greeting", {}).get("text") if isinstance(input_obj.get("greeting"), dict) else None
                        base = base or input_obj.get("text") or ""
                        return base or ""
                    if t == "number":
                        return 0
                    if t == "boolean":
                        return False
                    return {}
                cand = {}
                for k in schema_dict.get("required", []):
                    cand[k] = _default_for(props.get(k))
                # Nice touch: if there's a 'text' field, append a mock suffix
                if "text" in cand and isinstance(cand["text"], str):
                    base = cand["text"] or input_obj.get("greeting", {}).get("text") or input_obj.get("text") or "Hello"
                    cand["text"] = f"{base} 👋 (mock)"
            # strict validation
            validate_against_shape(cand, schema_name, shapes)
            return cand
        except Exception as e:
            last_err = e
            # Construct a structured critique for the next attempt (provider allowing)
            critique = {
                "error": str(e),
                "expected_schema": schema_dict,
                "example": {k: ("string" if v.get("type")=="string" else 0) for k, v in schema_dict.get("properties", {}).items()}
            }
            # If we have another attempt, wrap the input with the critique
            input_obj = {"original": input_obj, "critique": critique}
            continue
    # Exhausted retries
    raise RuntimeError(f"LLM failed schema validation after {retries} attempts: {last_err}")


def exec_fn(fn, shapes, fns, inbound=None):
    env, result = {}, None
    # Bind inbound struct to any declared input names
    if inbound is not None:
        declared_inputs = (fn.get("in") or {})
        if declared_inputs:
            input_names = list(declared_inputs.keys())
            # If inbound is a dict and contains the declared key, use that; otherwise:
            if isinstance(inbound, dict):
                if len(input_names) == 1 and input_names[0] in inbound:
                    env[input_names[0]] = inbound[input_names[0]]
                else:
                    for name in input_names:
                        env[name] = inbound
            else:
                # Non-dict inbound: if single input param, map directly to it
                if len(input_names) == 1:
                    env[input_names[0]] = inbound

    # @const
    for k, v in fn.get("@const", {}).items():
        env[k] = v

    # @op
    explain = bool(os.getenv("ALP_EXPLAIN"))
    for idx, op in enumerate(fn.get("@op", [])):
        name, args = op[0], (op[1] if len(op) > 1 else {})
        bind_meta = (op[2] if len(op) > 2 and isinstance(op[2], dict) else {})
        a = resolve_args(args, env)
        if name == "add":
            result = op_add(a)
        elif name == "sub":
            result = op_sub(a)
        elif name == "mul":
            result = op_mul(a)
        elif name == "div":
            result = op_div(a)
        elif name == "pow":
            result = op_pow(a)
        elif name == "neg":
            result = op_neg(a)
        elif name == "min":
            result = op_min(a)
        elif name == "max":
            result = op_max(a)
        elif name == "abs":
            result = op_abs(a)
        elif name == "round":
            result = op_round(a)
        elif name == "sum":
            result = op_sum(a)
        elif name == "avg":
            result = op_avg(a)
        elif name == "concat":
            items = a.get("items")
            if items is not None:
                result = "".join(str(x) for x in items)
            else:
                result = str(a.get("a", "")) + str(a.get("b", ""))
        elif name == "join":
            items = a.get("items") or []
            sep = str(a.get("sep", ""))
            result = sep.join(str(x) for x in items)
        elif name == "split":
            text = str(a.get("text", ""))
            sep = str(a.get("sep", ","))
            result = text.split(sep)
        elif name == "calc_eval":
            result = op_calc_eval(a)
        elif name == "to_calc_result":
            result = op_to_calc_result(a)
        elif name == "map_each":
            items = a.get("items") or []
            target_id = a.get("fn")
            if not target_id or target_id not in fns:
                raise RuntimeError("map_each requires valid 'fn' id")
            target = fns[target_id]
            param = a.get("param")  # optional explicit param name
            mapped = []
            for it in items:
                inbound_item = it
                # If an explicit param name is provided, wrap into dict for clarity
                if param is not None:
                    inbound_item = {param: it}
                r, _ = exec_fn(target, shapes, fns, inbound=inbound_item)
                mapped.append(r)
            result = mapped
        elif name == "read_file":
            result = op_read_file(a)
        elif name == "write_file":
            result = op_write_file(a)
        elif name == "http":
            result = op_http(a)
        elif name == "json_parse":
            result = op_json_parse(a)
        elif name == "json_get":
            result = op_json_get(a)
        else:
            raise RuntimeError(f"Unknown op: {name}")
        # expose the latest result to subsequent ops
        env["result"] = result
        if isinstance(result, dict) and "value" in result:
            env["value"] = result["value"]
        elif isinstance(result, (int, float)):
            env["value"] = result
        # named binding
        if bind_meta.get("as"):
            env[bind_meta["as"]] = result
        if explain:
            try:
                print(json.dumps({
                    "node": fn.get("id"),
                    "op_index": idx,
                    "op": name,
                    "env_snapshot": {k: (v if isinstance(v, (int,float,str,bool)) else type(v).__name__) for k, v in env.items()}
                }, indent=2), file=sys.stderr)
            except Exception:
                pass

    # @llm
    if "@llm" in fn:
        spec = fn["@llm"]
        task = spec.get("task")
        inp  = resolve_args(spec.get("input") or {}, env)
        if not inp and inbound is not None:
            inp = inbound
        result = call_llm(task, inp, spec.get("schema"), shapes, retries=(fn.get("@retry", {}) or {}).get("max", 3))
        env["result"] = result
        if isinstance(result, dict) and "value" in result:
            env["value"] = result["value"]

    # @expect
    exp_type = (fn.get("@expect") or {}).get("type")
    if exp_type:
        # If result isn't already an object, try to synthesize it from env
        if result is None or not isinstance(result, dict):
            shape_def = _get_shape_def(exp_type, shapes)
            fields = shape_def.get("fields", {})
            synthesized = {}
            for k in fields.keys():
                key = k[:-1] if k.endswith("?") else k
                if key in env:
                    synthesized[key] = env[key]
            if synthesized:
                result = synthesized
        # Apply defaults before validation
        if isinstance(result, dict):
            result = _apply_shape_defaults(result, exp_type, shapes)
        if "@llm" not in fn:
            # reuse strict validator for consistency
            validate_against_shape(result, exp_type, shapes)

    trace = {
        "node": fn.get("id"),
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "outputs_hash": hash_obj(result),
        "status": "ok"
    }
    return result, trace

def run(path):
    shapes, fns, flow = load_graph(path)
    if not flow:
        # fallback to any no-input fn
        for k, fn in fns.items():
            if not fn.get("in"):
                flow = [[k, None, {}]]
                break
    if not flow:
        raise RuntimeError("No runnable nodes.")

    traces = []
    data_out = None
    # execute flow linearly: src -> dst -> ...
    # pick first edge's source as start and follow chain
    # we’ll just iterate edges in order for this stub
    def resolve_from_obj(ref, obj):
        if isinstance(ref, str) and ref.startswith("$"):
            key = ref[1:]
            parts = key.split(".") if "." in key else [key]
            cur = obj
            for p in parts:
                if isinstance(cur, dict) and p in cur:
                    cur = cur[p]
                elif p == "value" and not isinstance(cur, dict):
                    cur = cur
                else:
                    return None
            return cur
        return ref

    def eval_when(cond, obj):
        if cond is None:
            return True
        if isinstance(cond, bool):
            return cond
        if isinstance(cond, str):
            val = resolve_from_obj(cond, obj)
            return bool(val)
        if isinstance(cond, dict):
            if len(cond) != 1:
                return False
            op_name, arg = next(iter(cond.items()))
            if op_name in ("and", "or") and isinstance(arg, list):
                vals = [eval_when(x, obj) for x in arg]
                return all(vals) if op_name == "and" else any(vals)
            if op_name == "not":
                return not eval_when(arg, obj)
            if isinstance(arg, list) and len(arg) == 2:
                left = resolve_from_obj(arg[0], obj)
                right = resolve_from_obj(arg[1], obj)
                if op_name == "eq":
                    return left == right
                elif op_name == "ne":
                    return left != right
                elif op_name == "gt":
                    return left > right
                elif op_name == "gte":
                    return left >= right
                elif op_name == "lt":
                    return left < right
                elif op_name == "lte":
                    return left <= right
        return False

    for src, dst, meta in flow:
        fn = fns[src]
        result, tr = exec_fn(fn, shapes, fns, inbound=data_out)
        traces.append(tr)
        data_out = result
        if dst:
            when_cond = (meta or {}).get("when") if isinstance(meta, dict) else None
            if eval_when(when_cond, data_out):
                fn2 = fns[dst]
                result2, tr2 = exec_fn(fn2, shapes, fns, inbound=data_out)
                traces.append(tr2)
                data_out = result2

    print(json.dumps({"result": data_out, "trace": traces}, indent=2))

if __name__ == "__main__":
    run(sys.argv[1])
