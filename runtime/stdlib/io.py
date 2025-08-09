import os
import sys


def register(reg):
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

    def read_file(a, ctx):
        path = a.get("path")
        if not isinstance(path, str) or not path:
            raise RuntimeError("read_file requires 'path'")
        root = _io_root()
        abs_path = _safe_path_join(root, path)
        encoding = a.get("encoding") or "utf-8"
        with open(abs_path, "r", encoding=encoding) as f:
            text = f.read()
        return {"text": text}

    def write_file(a, ctx):
        if not _io_allow_write():
            raise RuntimeError("Writes disabled. Set ALP_IO_ALLOW_WRITE=1 to enable.")
        path = a.get("path")
        text = a.get("text", "")
        if not isinstance(path, str) or not path:
            raise RuntimeError("write_file requires 'path'")
        root = _io_root()
        abs_path = _safe_path_join(root, path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        encoding = a.get("encoding") or "utf-8"
        mode = "a" if a.get("append") else "w"
        with open(abs_path, mode, encoding=encoding) as f:
            f.write(str(text))
        return {"ok": True}

    def read_stdin(a, ctx):
        allow = os.getenv("ALP_STDIN_ALLOW", "0") in ("1", "true", "yes")
        if not allow:
            raise RuntimeError("Stdin reads disabled. Set ALP_STDIN_ALLOW=1 to enable.")
        mode = (a.get("mode") or "all").lower()
        try:
            max_bytes = int(a.get("max_bytes") or os.getenv("ALP_STDIN_MAX_BYTES", "1000000"))
        except Exception:
            max_bytes = 1000000
        if mode == "line":
            line = sys.stdin.readline()
            return {"text": line[:max_bytes]}
        data = sys.stdin.read(max_bytes)
        return {"text": data}

    reg("read_file", read_file); reg("write_file", write_file); reg("read_stdin", read_stdin)
