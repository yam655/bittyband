#!/usr/bin/env python3

__all__ = ["KeyMaps"]

from .config import ConfigError
import sys
import unicodedata

class KeyMaps:
    keymap = None
    def __init__(self, config):
        self.keymap = self.map_keys(config)

    def test(self):
        sys.stdout.write(repr(self.keymap))

    def map_keys(self, config):
        keymap = {}
        for value in config["keymap"].keys():
            if value in config["DEFAULT"]:
                continue
            ks = config["keymap"][value].strip()
            keys = []
            if ks == "":
                continue
            elif ks[0] == "(" and ks[-1] == ")":
                keys = comma_split(ks[1:-1])
            elif ks[0] == '"' and ks[-1] == '"':
                keys = ks[1:-1]
            elif ks[0] == "'" and ks[-1] == "'":
                keys = ks[1:-1]
            else:
                keys = ks
            if isinstance(keys, str):
                keymap[expand_unicode(keys)] = value
            else:
                for key in keys:
                    keymap[expand_unicode(key)] = value
        return keymap

def expand_unicode(s):
    """ Convert unicode reference in to a Unicode string. """
    if s.startswith(r'\u') or s.startswith(r'\U'):
        return chr(int(s,16))
    if s.startswith(r'\N{'):
        name = s[3:-1]
        try:
            return unicodedata.lookup(name)
        except:
            raise ConfigError("Failed to find unicode value with name {}\n".format(name))
    else:
        return s

def comma_split(what):
    """ Split on commas and/or quotes """
    ret = []
    check = what[0]
    # parts = (what, "", "")
    if check == "'" or check == '"':
        parts = what.partition(check)
    else:
        parts = what.partition(",")
    ret.append(parts[0])
    while len(parts[-1]) > 0:
        what = parts[-1]
        i = 0
        while i < len(what) and (what[i].isspace() or what[i] == ','):
            i += 1
        if i < len(what):
            check = what[i]
            if check == "'" or check == '"':
                parts = what[i:].partition(check)
            else:
                parts = what[i:].partition(",")
            ret.append(parts[0])
    return ret


