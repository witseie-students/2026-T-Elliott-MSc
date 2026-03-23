"""
Tiny helpers that don’t belong elsewhere.
"""

import shutil

_TERM_WIDTH = shutil.get_terminal_size((100, 20)).columns

def pretty_print(level: int, tag: str, msg: str) -> None:
    """
    Light ASCII tree logger.  
    Re‑flows long lines so console output stays tidy.
    """
    prefix = ("│   " * level) + ("├─ " if level else "") + f"{tag}: "
    room   = _TERM_WIDTH - len(prefix) - 1
    cut    = (msg[: room - 3] + "…") if len(msg) > room else msg
    print(prefix + cut, flush=True)
