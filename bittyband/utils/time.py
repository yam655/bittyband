#!/usr/bin/env python3

__all__ = ["human_duration", "reasonable_time"]

import time


def human_duration(seconds):
    if seconds is None:
        return "??:??"
    if isinstance(seconds, str):
        seconds = float(seconds)

    tiny = ""
    tiny_bit = seconds % 1.0
    if tiny_bit > 0:
        tiny = "{:.3f}".format(tiny_bit)[1:]
    out = "{:02d}{}".format(int(seconds) % 60, tiny)
    n = seconds // 60
    if n > 0:
        out = "{:02d}:{}".format(int(n) % 60, out)
        n //= 60
    else:
        out = "00:{}".format(out)
    if n > 0:
        out = "{:02d}:{}".format(int(n) % 24, out)
        n //= 24
    if n > 0:
        out = "{}:{}".format(n, out)
    return out


def reasonable_time(seconds):
    return time.strftime("(%a) %Y-%m-%d %H:%M", time.localtime(seconds))
