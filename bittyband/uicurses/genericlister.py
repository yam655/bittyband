#!/usr/bin/env python3

import curses
import curses.ascii
import locale

from ..errors import ConfigError

locale.setlocale(locale.LC_ALL, '')
_code = locale.getpreferredencoding()

_INDICATOR_OFFSET = 2


class FieldReader:
    def __init__(self, getcher, stdscr, y, x1, x2):
        self.stdscr = stdscr
        self.getcher = getcher
        self.y = y
        self.x1 = x1
        self.data = []
        self.x2 = x2
        self.cursor = x1
        self.next_of_kind = False
        self.apply_change = False

    def move(self, x = None):
        if x is not None:
            if x < self.x1 or x >= self.x2:
                return
            self.stdscr.chgat(self.y, self.cursor, 1, curses.A_NORMAL)
            self.cursor = x
        self.stdscr.chgat(self.y, self.cursor, 1, curses.A_REVERSE)

    def do_command(self, key):
        # self.lastcmd = ch
        if len(key) == 1:
            if self.cursor < self.x2:
                if self.cursor - self.x1 == len(self.data):
                    self.data.append(key)
                    self.stdscr.addstr(self.y, self.cursor, key)
                else:
                    self.data.insert(self.cursor - self.x1, key)
                    self.refresh()
                self.move(self.cursor + 1)
        elif key == "^A":
            self.move(self.x1)
            self.refresh()
        elif key in ("^B", "KEY_LEFT", "^H", "KEY_BACKSPACE", "^?"):
            if self.cursor == 0:
                return False
            self.move(self.cursor - 1)
            if key in ("^H", "KEY_BACKSPACE", "^?"):
                self.stdscr.delch()
                del self.data[self.cursor - self.x1]
            self.refresh()
        elif key == "^D":
            self.stdscr.delch()
            del self.data[self.cursor - self.x1]
            self.refresh()
        elif key == "^E":
            self.move(self.x1 + len(self.data))
            self.refresh()
        elif key in ("^F", "KEY_RIGHT"):
            if self.cursor < self.x2 and self.cursor - self.x1 < len(self.data):
                self.move(self.cursor + 1)
                self.refresh()
        elif key in "^G":
            raise GetStrInterrupt()
        elif key in ("^J", "KEY_ENTER"):
            return False
        elif key == "^I":
            self.next_of_kind = True
            return False
        elif key == "^R":
            self.apply_change = True
            return False
        elif key == "^K":
            self.data = self.data[:self.cursor - self.x1]
            self.refresh()
        elif key == "^L":
            self.refresh()
        elif key in ("^N", "KEY_DOWN"):
            buf = "".join(self.data)
            i = self.cursor - self.x1
            if i < len(buf):
                if buf[i].isspace():
                    while i < len(buf) and buf[i].isspace():
                        i += 1
                while i < len(buf) and not buf[i].isspace():
                    i += 1
                self.move(i + self.x1)
                self.stdscr.refresh()
        elif key in ("^P", "KEY_UP"):
            buf = "".join(self.data)
            i = self.cursor - self.x1
            if i > 0:
                if i >= len(buf):
                    i = len(buf) - 1
                if buf[i].isspace():
                    while i >= 0 and buf[i].isspace():
                        i -= 1
                while i >= 0 and not buf[i].isspace():
                    i -= 1
                self.move(i + self.x1)
                self.stdscr.refresh()
        return True

    def refresh(self):
        self.stdscr.move(self.y, self.x1)
        self.stdscr.addstr("".join(self.data))
        self.stdscr.clrtoeol()
        self.move()
        self.stdscr.refresh()

    def get(self, initial=""):
        self.data = list(initial)
        self.cursor = self.x1 + len(initial)
        self.refresh()
        ret = initial
        try:
            while 1:
                key = self.getcher.get_key()
                if not self.do_command(key):
                    ret = "".join(self.data)
                    break
        except GetStrInterrupt:
            ret = initial
        self.stdscr.move(self.y, self.x1)
        self.stdscr.clrtoeol()
        self.stdscr.refresh()
        return ret

class GetStrInterrupt(Exception):
    pass

class GenericLister:
    def __init__(self, config):
        self.stdscr = None
        self.active = 0
        self.top = 0
        self.keymap = {}
        self.running = False
        self.ui = None
        self.invalidate = False
        self.next_of_kind = False
        self.apply_change = False

    def wire(self, *, logic, ui, **kwargs):
        self.ui = ui
        self.keymap.clear()
        self._register_builtins()
        self.logic = kwargs[logic]
        self.logic.prepare_keys(self)

    def refresh_status(self, *, no_refresh=False):
        max_y, max_x = self.stdscr.getmaxyx()
        self.stdscr.hline(max_y - 2, 0, "=", max_x)
        if not no_refresh:
            self.stdscr.refresh()

    def refresh_line(self, line, *, no_refresh=False):
        if self.invalidate:
            self.refresh()
            return
        if len(self.logic.get_order()) == 0:
            return
        max_y, max_x = self.stdscr.getmaxyx()
        row = line - self.top
        if row < 0 or row >= max_y:
            return
        bit = self.logic.get_order()[line]
        title = self.logic.get_line(bit, max_x - _INDICATOR_OFFSET * 2)
        if line == self.active:
            self.stdscr.addstr(row, 0, ">  ", curses.A_REVERSE)
            self.stdscr.addstr(row, _INDICATOR_OFFSET, title, curses.A_REVERSE)
            self.stdscr.chgat(row, 0, curses.A_REVERSE)
        else:
            self.stdscr.addstr(row, _INDICATOR_OFFSET, title)
            self.stdscr.chgat(row, 0, curses.A_NORMAL)
        if not no_refresh:
            self.stdscr.refresh()

    def refresh(self):
        global _INDICATOR_OFFSET
        self.invalidate = False
        self.stdscr.clear()
        max_y, max_x = self.stdscr.getmaxyx()
        max_y -= 2
        self.refresh_status(no_refresh=True)
        if len(self.logic.get_order()) == 0:
            self.stdscr.addstr(0, 0, ">  ", curses.A_REVERSE)
            self.stdscr.chgat(0, 0, curses.A_REVERSE)
            self.stdscr.addstr(0, _INDICATOR_OFFSET, "<no data>", curses.A_REVERSE)
            return
        for y in range(0, max_y):
            if y + self.top >= len(self.logic.get_order()):
                break
            self.refresh_line(y + self.top, no_refresh=True)
        self.stdscr.refresh()

    def show_status(self, what=""):
        if what is None:
            what = ""
        y = self.stdscr.getmaxyx()[0]
        self.stdscr.addstr(y - 1, 0, str(what))
        self.stdscr.clrtoeol()
        self.stdscr.refresh()

    def read_string(self, prompt="", initial=""):
        global _code
        max_y, max_x = self.stdscr.getmaxyx()
        self.stdscr.addstr(max_y - 2, 0, prompt)
        self.stdscr.addstr(" ")
        self.stdscr.move(max_y - 1, 0)
        self.stdscr.clrtoeol()
        self.stdscr.refresh()
        fr = FieldReader(self, self.stdscr, max_y - 1, 0, max_x)
        s = fr.get(initial)
        self.next_of_kind = fr.next_of_kind
        self.apply_change = fr.apply_change
        self.stdscr.hline(max_y - 2, 0, "=", max_x)
        self.stdscr.addstr(" ")
        self.stdscr.move(max_y - 1, 0)
        self.stdscr.clrtoeol()
        return s

    def add_variant(self, orig_key, new_key):
        self.keymap[orig_key].keys.append(new_key)
        self.keymap[new_key] = self.keymap[orig_key]

    def register_key(self, function, key, *variants, prompt="Enter value:", arg=None, description=None, query=False):
        keys = [key]
        keys.extend(variants)
        entry = KeyEntry(function=function, prompt=prompt, arg=arg, keys=keys, description=description, query=query)
        self.keymap[key] = entry
        for k in variants:
            self.keymap[k] = entry

    def _quit_cmd(self, line):
        self.running = False
        return False

    def _up_cmd(self, line):
        self.move_to(self.active - 1)
        return False

    def _down_cmd(self, line):
        self.move_to(self.active + 1)
        return False

    def _help_cmd(self, line):
        return True

    def _refresh_cmd(self, line):
        self.invalidate = True
        return True

    def _register_builtins(self):
        self.register_key(self._quit_cmd, "Q", "q", "^]",
                          description="Quit")
        self.register_key(self._down_cmd, "KEY_DOWN",
                          description="Move down a row")
        self.register_key(self._up_cmd, "KEY_UP",
                          description="Move up a row")
        self.register_key(self._refresh_cmd, "^L", "^R",
                          description="Refresh the window")
        self.register_key(self._help_cmd, "?",
                          description="Show this help text")

    def get_key(self):
        return self.ui.get_key()

    def __call__(self, stdscr):
        self.stdscr = stdscr
        self.stdscr.keypad(True)
        self.logic.scan()
        self.refresh()
        self.running = True

        while self.running:
            ch = self.get_key()
            if ch in self.keymap:
                entry = self.keymap[ch]
                if entry.arg is None:
                    if entry.function(line=self.active):
                        self.refresh_line(self.active)
                elif entry.arg == "<self>":
                    if entry.function(self, line=self.active):
                        self.refresh_line(self.active)
                elif entry.arg == "?str":
                    initial = ""
                    self.next_of_kind = True
                    while self.next_of_kind or self.apply_change:
                        if entry.query:
                            initial = entry.function(None, line=-self.active)
                        s = self.read_string(entry.prompt, initial=initial)
                        if s is not None:
                            if entry.function(s, line=self.active):
                                self.refresh_line(self.active)
                        if self.next_of_kind:
                            self.move_to(self.active + 1)
                elif entry.arg == "...slow":
                    self.show_status(entry.prompt)
                    if entry.function(line=self.active):
                        self.refresh_line(self.active)
                    else:
                        self.show_status()
                elif entry.arg == "?yN":
                    s = self.read_string(entry.prompt)
                    if s == "Y" or s == "y":
                        if entry.function(line=self.active):
                            self.refresh_line(self.active)
                    else:
                        self.show_status("Skipped.")
                elif entry.arg == "?Yn":
                    s = self.read_string(entry.prompt)
                    if s != "N" and s != "n":
                        if entry.function(line=self.active):
                            self.refresh_line(self.active)
                    else:
                        self.show_status("Skipped.")

                self.stdscr.refresh()
            else:
                self.show_status("Unknown key: {}".format(ch))

    def move_to(self, line):
        old_active = self.active
        self.active = line
        max_y = self.stdscr.getmaxyx()[0] - 2
        self.stdscr.addstr(old_active - self.top, 0, " ")
        old_top = self.top
        if self.active < 0:
            self.active = len(self.logic.get_order()) - 1
            self.top = self.active - max_y // 2
            if self.top < 0:
                self.top = 0
        elif self.active - self.top < 0:
            self.top -= max_y // 2
            if self.top < 0:
                self.top = 0
        elif self.active >= len(self.logic.get_order()):
            self.active = 0
            self.top = 0
        elif self.active - self.top >= max_y:
            self.top += max_y // 2
            if self.top >= len(self.logic.get_order()):
                self.top = 0
        if old_top != self.top:
            self.refresh()
        else:
            self.refresh_line(old_active, no_refresh=True)
            self.refresh_line(self.active, no_refresh=True)
            self.stdscr.refresh()


class KeyEntry:
    def __init__(self, *, function, keys, prompt, arg, description, query):
        self.function = function
        self.keys = keys
        self.prompt = prompt
        self.arg = arg
        self.description = description
        self.query = query
