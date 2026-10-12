"""ANSI escape codes and named operator styles."""

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"

STYLE_CODES = {
    "ok": (GREEN,),
    "warn": (YELLOW,),
    "error": (RED, BOLD),
    "info": (CYAN,),
}
