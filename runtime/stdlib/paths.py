import os


def register(reg):
    def path_basename(a, ctx):
        p = a.get("path") or ""
        if not isinstance(p, str):
            raise RuntimeError("path_basename requires 'path' string")
        return os.path.basename(p)

    reg("path_basename", path_basename)
