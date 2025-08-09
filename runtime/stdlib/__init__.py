from . import math as math
from . import strings as strings
from . import strings_extra as strings_extra
from . import jsonlib as jsonlib
from . import io as io
from . import http as http
from . import paths as paths
from . import iter as iterlib
from . import llm as llm


def register_all(ops_registry: dict, register_op):
    for mod in (math, strings, strings_extra, jsonlib, io, http, paths, iterlib, llm):
        if hasattr(mod, "register"):
            mod.register(register_op)
