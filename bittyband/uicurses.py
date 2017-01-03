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
    
    def __init__(self, config, keymaps, commands, cmdrecorder):
        self.config = config
        self.keymap = keymaps.keymap
        self.commands = commands
        self.cmdrecorder = cmdrecorder

    def jam(self): 
        curses.wrapper(self._jam)

    def _jam(self, stdscr):
        stdscr.keypad(True)
        stdscr.scrollok(True)

        self.stdscr = stdscr
        ch = stdscr.getkey()
        command = self.keymap.get(ch)
        first_preset = "preset_0"
        self.commands.execute(first_preset, ui=self)
        self.cmdrecorder.start()
        self.cmdrecorder.add(first_preset)
        while command != "quit":
            if command is not None:
                self.cmdrecorder.add(command)
                self.commands.execute(command, ui=self)
            else:
                self.putln("Unknown key: '{}' (len:{})".format(ch, len(ch)))
            ch = stdscr.getkey()
            command = self.keymap.get(ch)
        self.commands.do_panic()
        self.cmdrecorder.add("panic")
        self.cmdrecorder.end()

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


