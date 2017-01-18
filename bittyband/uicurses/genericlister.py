#!/usr/bin/env python3

import curses
import locale

from ..errors import ConfigError

locale.setlocale(locale.LC_ALL, '')
_code = locale.getpreferredencoding()

_INDICATOR_OFFSET = 2


class GenericLister:
    def __init__(self, config):
        self.stdscr = None
        self.active = 0
        self.top = 0
        self.keymap = {}
        self.running = False
        self.ui = None

    def wire(self, *, logic, ui, **kwargs):
        self.ui = ui
        self.keymap.clear()
        self._register_builtins()
        self.logic = kwargs[logic]
        self.logic.prepare_keys(self)

    def refresh_status(self):
        max_y, max_x = self.stdscr.getmaxyx()
        self.stdscr.hline(max_y - 2, 0, "=", max_x)

    def refresh(self):
        global _INDICATOR_OFFSET
        self.stdscr.clear()
        max_y, max_x = self.stdscr.getmaxyx()
        self.refresh_status()
        if len(self.logic.get_order()) == 0:
            self.stdscr.addstr(0, 0, ">  ", curses.A_REVERSE)
            self.stdscr.chgat(0, 0, curses.A_REVERSE)
            self.stdscr.addstr(0, _INDICATOR_OFFSET, "<no data>", curses.A_REVERSE)
            return
        max_y, max_x = self.stdscr.getmaxyx()
        max_y -= 2
        for y in range(0, max_y):
            if y + self.top >= len(self.logic.get_order()):
                break
            bit = self.logic.get_order()[y+self.top]
            title = self.logic.get_line(bit, max_x - _INDICATOR_OFFSET * 2)
            if y + self.top == self.active:
                self.stdscr.addstr(self.active - self.top, 0, ">  ", curses.A_REVERSE)
                self.stdscr.addstr(y, _INDICATOR_OFFSET, title, curses.A_REVERSE)
                self.stdscr.chgat(y, 0, curses.A_REVERSE)
            else:
                self.stdscr.addstr(y, _INDICATOR_OFFSET, title)
        self.stdscr.refresh()

    def show_status(self, what=""):
        if what is None:
            what = ""
        y = self.stdscr.getmaxyx()[0]
        self.stdscr.addstr(y - 1, 0, str(what))
        self.stdscr.clrtoeol()
        self.stdscr.refresh()

    def read_string(self, prompt=""):
        global _code
        max_y, max_x = self.stdscr.getmaxyx()
        self.stdscr.addstr(max_y - 2, 0, prompt)
        self.stdscr.addstr(" ")
        self.stdscr.move(max_y - 1, 0)
        self.stdscr.clrtoeol()
        self.stdscr.refresh()
        curses.echo()
        s = self.stdscr.getstr(max_y - 1, 0)
        curses.noecho()
        self.stdscr.hline(max_y - 2, 0, "=", max_x)
        self.stdscr.addstr(" ")
        self.stdscr.move(max_y - 1, 0)
        self.stdscr.clrtoeol()
        return str(s, _code)

    def add_variant(self, orig_key, new_key):
        self.keymap[orig_key].keys.append(new_key)
        self.keymap[new_key] = self.keymap[orig_key]

    def register_key(self, function, key, *variants, prompt="Enter value:", arg=None, description=None):
        keys = [key]
        keys.extend(variants)
        entry = KeyEntry(function=function, prompt=prompt, arg=arg, keys=keys, description=description)
        self.keymap[key] = entry
        for k in variants:
            self.keymap[k] = entry

    def _quit_cmd(self, line):
        self.running = False
        return False

    def _up_cmd(self, line):
        self.active -= 1
        return False

    def _down_cmd(self, line):
        self.active += 1
        return False

    def _help_cmd(self, line):
        return True

    def _refresh_cmd(self, line):
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
            old_active = self.active
            if ch in self.keymap:
                entry = self.keymap[ch]
                if entry.arg is None:
                    if entry.function(line=self.active):
                        self.refresh()
                elif entry.arg == "<self>":
                    if entry.function(self, line=self.active):
                        self.refresh()
                elif entry.arg == "?str":
                    s = self.read_string(entry.prompt)
                    if s is not None:
                        if entry.function(s, line=self.active):
                            self.refresh()
                elif entry.arg == "...slow":
                    self.show_status(entry.prompt)
                    if entry.function(line=self.active):
                        self.refresh()
                    else:
                        self.show_status()
                elif entry.arg == "?yN":
                    s = self.read_string(entry.prompt)
                    if s == "Y" or s == "y":
                        if entry.function(line=self.active):
                            self.refresh()
                    else:
                        self.show_status("Skipped.")
                elif entry.arg == "?Yn":
                    s = self.read_string(entry.prompt)
                    if s != "N" and s != "n":
                        if entry.function(line=self.active):
                            self.refresh()
                    else:
                        self.show_status("Skipped.")

                self.stdscr.refresh()
            else:
                self.show_status("Unknown key: {}".format(ch))

            if old_active == -1:
                self.active = old_active
            elif old_active != self.active:
                max_y = self.stdscr.getmaxyx()[0] - 2
                self.stdscr.addstr(old_active - self.top, 0, " ")
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
                self.refresh()


class KeyEntry:
    def __init__(self, *, function, keys, prompt, arg, description):
        self.function = function
        self.keys = keys
        self.prompt = prompt
        self.arg = arg
        self.description = description