import subprocess
import sys
from pathlib import Path
import json
import os

# Execute the VM stub on the provided program (default: hello_world.alp)
vm_path = str(Path(__file__).parent.joinpath("runtime","alp_vm.py"))
program_path = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).parent.joinpath("examples","hello_world.alp"))

def _get_by_path(obj, path):
  cur = obj
  for part in path.split('.'):
    if isinstance(cur, dict) and part in cur:
      cur = cur[part]
    elif isinstance(cur, list):
      try:
        idx = int(part)
      except Exception:
        return None
      if idx < 0 or idx >= len(cur):
        return None
      cur = cur[idx]
    else:
      return None
  return cur

if program_path.endswith(".jsonl"):
    # simple golden runner
    ok = True
    for line in Path(program_path).read_text().splitlines():
        if not line.strip():
            continue
        t = json.loads(line)
        prog = str(Path(__file__).parent.joinpath(t["program"]))
        expected = t.get("expect")
        env = os.environ.copy()
        for k, v in (t.get("env") or {}).items():
            env[str(k)] = str(v)
        run = subprocess.run([sys.executable, vm_path, prog], capture_output=True, text=True, env=env)
        out = json.loads(run.stdout)
        # Flexible matching: exact, result equality, expectKeys existence, or expectContains substrings
        match = False
        if expected is None:
            match = True
        elif out == expected or out.get("result") == (expected or {}).get("result"):
            match = True
        else:
            keys = t.get("expectKeys") or []
            if keys:
                match = all(_get_by_path(out, k) is not None for k in keys)
            contains = t.get("expectContains") or {}
            if not match and contains:
                ok = True
                for path, substr in contains.items():
                    val = _get_by_path(out, path)
                    if not isinstance(val, str) or str(substr) not in val:
                        ok = False
                        break
                match = ok
        status = "OK" if match else "FAIL"
        print(json.dumps({"program": t["program"], "status": status, "output": out}, indent=2))
        if not match:
            ok = False
    sys.exit(0 if ok else 1)
else:
    completed = subprocess.run([sys.executable, vm_path, program_path], capture_output=True, text=True)
    print(completed.stdout)
    if completed.stderr:
        print(completed.stderr)