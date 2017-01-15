#!/usr/bin/env python3

try:
    import curses
except ImportError:
    curses = None

from curses import ascii
from pathlib import Path
import locale

from .genericlister import generic_lister

locale.setlocale(locale.LC_ALL, '')
code = locale.getpreferredencoding()


def is_available():
    return curses is not None


class UiCurses:
    keymap = None

    def __init__(self, *, config, keymaps=None, commands=None, cmdrecorder=None, lister=None, importer=None, player=None):
        self.project_dir = Path(config["instance"]["project_dir"])
        self.config = config
        if keymaps is not None:
            self.keymap = keymaps.keymap
        self.commands = commands
        self.cmdrecorder = cmdrecorder
        self.lister = lister
        self.importer = importer
        self.player = player

    def jam(self):
        curses.wrapper(self._jam)

    def list_it(self):
        generic_lister(self.lister)

    def import_it(self):
        generic_lister(self.importer)

    def read_string(self, prompt=""):
        global code
        y = self.stdscr.getmaxyx()[0]
        self.stdscr.addstr(y - 2, 0, prompt)
        self.stdscr.clrtoeol()
        self.stdscr.move(y - 1, 0)
        self.stdscr.clrtoeol()
        self.stdscr.refresh()
        curses.echo()
        s = self.stdscr.getstr(y - 1, 0)
        curses.noecho()
        return str(s, code)

    def _import(self, stdscr):
        stdscr.keypad(True)
        stdscr.scrollok(True)
        self.stdscr = stdscr
        self._pick_import_file()

    def _jam(self, stdscr):
        stdscr.keypad(True)
        stdscr.scrollok(True)

        self.stdscr = stdscr
        ch = ""
        command = ""
        self.cmdrecorder.add("mark_good")
        first_preset = "preset_0"
        self.commands.execute(first_preset, ui=self)
        self.cmdrecorder.add(first_preset)

        while command != "quit":
            if command is None:
                self.putln("Unknown key: '{}' (len:{})".format(ch, len(ch)))
            elif command != "":
                self.cmdrecorder.add(command)
                self.commands.execute(command, ui=self)
            ch = stdscr.getkey()
            command = self.keymap.get(ch)
        self.commands.do_silence("silence")
        self.commands.do_panic()
        self.cmdrecorder.add("mark_bad")

    def puts(self, something):
        maxx = self.stdscr.getmaxyx()[1]
        x = self.stdscr.getyx()[1]
        if x > maxx - 10:
            self.stdscr.addstr("\n")
        self.stdscr.addstr(something)
        self.stdscr.refresh()

    def putln(self, something):
        self.stdscr.addstr(something)
        self.stdscr.addstr("\n")
        self.stdscr.refresh()
