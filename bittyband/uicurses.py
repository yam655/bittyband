#!/usr/bin/env python3

__all__ = ["CursesUi"]

import sys

try:
    import curses
except:
    curses = None

import locale
locale.setlocale(locale.LC_ALL, '')
code = locale.getpreferredencoding()

def is_available():
    return curses is not None

class UiCurses:
    keymap = None
    
    def __init__(self, config, keymaps, commands):
        self.config = config
        self.keymap = keymaps.keymap
        self.commands = commands

    def jam(self): 
        curses.wrapper(self._jam)

    def _jam(self, stdscr):
        stdscr.keypad(True)
        stdscr.scrollok(True)

        self.stdscr = stdscr
        ch = stdscr.getkey()
        command = self.keymap.get(ch)
        self.commands.execute("preset_0", ui=self)
        while command != "quit":
            if command is not None:
                self.commands.execute(command, ui=self)
            else:
                self.puts("Unknown key: '{}' (len:{})".format(ch, len(ch)))
            ch = stdscr.getkey()
            command = self.keymap.get(ch)
        self.commands.do_panic()

    def puts(self, something):
        self.stdscr.addstr(something)
        self.stdscr.addstr("\n")
        self.stdscr.refresh()


