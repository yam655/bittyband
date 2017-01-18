#!/usr/bin/env python3

__all__ = ["human_duration", "reasonable_time", "from_human_duration"]

import time

def from_human_duration(code):
    if code is None or isinstance(code, int) or isinstance(code,float):
        return code
    splits = code.split(":")
    ret = 0
    if len(splits) > 3:
        ret += float(splits[0])
        del splits[0]
    ret *= 24
    if len(splits) > 2:
        ret += float(splits[0])
        del splits[0]
    ret *= 60
    if len(splits) > 1:
        ret += float(splits[0])
        del splits[0]
    ret *= 60
    if len(splits) > 0:
        ret += float(splits[0])
    return ret

def human_duration(seconds, floor=-3):
    if seconds is None or seconds == "":
        return "??:??"
    if isinstance(seconds, str):
        if seconds.strip() == "":
            return "??:??"
        seconds = float(seconds)

    tiny = ""
    tiny_bit = seconds % 1.0
    if floor == 0:
        pass
    elif floor < 0:
        if tiny_bit > 0:
            tiny = "{:.{floor}f}".format(tiny_bit, floor=-floor)[1:]
    elif floor != True:
        tiny = "{:.{floor}f}".format(tiny_bit, floor=floor)[1:]
    out = "{:02d}{}".format(int(seconds) % 60, tiny)
    n = int(seconds) // 60
    if n > 0:
        out = "{:02d}:{}".format(n % 60, out)
        n //= 60
    else:
        out = "00:{}".format(out)
    if n > 0:
        out = "{:02d}:{}".format(int(n) % 24, out)
        n //= 24
    if n > 0:
        out = "{}:{}".format(int(n), out)
    return out


def reasonable_time(seconds, local=True):
    if isinstance(seconds, str):
        seconds = float(seconds)
    if local:
        t = time.localtime(seconds)
    else:
        t = time.gmtime(seconds)
    return time.strftime("(%a) %Y-%m-%d %H:%M", t)
