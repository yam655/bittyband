#!/usr/bin/env python3

__all__ = ["CursesUi"]

import sys

try:
    import curses
except:
    curses = None

from curses import ascii
from pathlib import Path
from .config import ConfigError

import locale
locale.setlocale(locale.LC_ALL, '')
code = locale.getpreferredencoding()

def is_available():
    return curses is not None

class UiCurses:
    keymap = None
    
    def __init__(self, config, keymaps, commands, cmdrecorder, lister=None):
        self.project_dir = Path(config["instance"]["project_dir"])
        self.config = config
        if keymaps is not None:
            self.keymap = keymaps.keymap
        self.commands = commands
        self.cmdrecorder = cmdrecorder
        self.lister = lister

    def jam(self): 
        curses.wrapper(self._jam)

    def list_it(self):
        curses.wrapper(self._list)

    def display_list(self):
        n = 0
        self.stdscr.clear()
        maxx = self.stdscr.getmaxyx()[1]
        for bit in self.lister.get_order():
            title = self.lister.get_title(bit, maxx - 6)
            self.stdscr.addstr(n, 3, title)
            n += 1

    def read_string(self, prompt=""):
        global code
        y = self.stdscr.getmaxyx()[0]
        self.stdscr.addstr(y-2, 0, prompt)
        self.stdscr.clrtoeol()
        self.stdscr.move(y-1,0)
        self.stdscr.clrtoeol()
        self.stdscr.refresh()
        curses.echo()
        s = self.stdscr.getstr(y-1,0)
        curses.noecho()
        return str(s, code)

    def _list(self, stdscr):
        stdscr.keypad(True)
        stdscr.scrollok(True)

        self.stdscr = stdscr
        self.lister.scan()
        self.display_list()
        line = 0
        ch = ""
        while ch != ascii.ESC:
            if ch == "q" or ch == "Q":
                break
            self.stdscr.addstr(line, 0, ">")
            ch = stdscr.getkey()
            if ch == "KEY_DOWN":
                self.stdscr.addstr(line, 0, " ")
                line += 1
            elif ch == "KEY_UP":
                self.stdscr.addstr(line, 0, " ")
                line -= 1
            elif ch == "r" or ch == "R":
                title = self.read_string("New title:")
                if title is not None or len(title).strip() > 0:
                    if title == "." or title == "-":
                        self.lister.rename(self.lister.get_order()[line], None)
                    else:
                        self.lister.rename(self.lister.get_order()[line], title)
                self.display_list()
            elif ch == "p" or ch == "P":
                material = self.lister.get(self.lister.get_order()[line])
                self.stdscr.addstr(line, 0, "P")
                self.stdscr.refresh()
                self.commands.play(material)
                self.stdscr.addstr(line, 0, ">")
                self.stdscr.refresh()
            elif ch == "d" or ch == "D":
                confirm = self.read_string("Really delete?")
                if len(confirm) > 0 and confirm[0] == "y" or confirm[0] == "Y":
                    self.lister.delete(self.lister.get_order()[line])
                self.display_list()

            elif ch == "m" or ch == "M":
                filenm = self.read_string("Export to MIDI:")
                self.stdscr.addstr(line, 0, "E")
                self.stdscr.refresh()
                if filenm is not None or len(filenm).strip() > 0:
                    markbit = self.lister.get_order()[line]
                    mark = self.lister.get_mark(markbit)
                    if filenm == "." or filenm == "-":
                        self.lister.export_midi(self.lister.get_order()[line], self.project_dir / "{}.midi".format(mark.get("title","export")))
                    else:
                        self.lister.export_midi(self.lister.get_order()[line], self.project_dir / filenm)
                self.display_list()
            elif ch == "l" or ch == "L":
                filenm = self.read_string("Export to Lilypond:")
                self.stdscr.addstr(line, 0, "E")
                self.stdscr.refresh()
                if filenm is not None or len(filenm).strip() > 0:
                    markbit = self.lister.get_order()[line]
                    mark = self.lister.get_mark(markbit)
                    if filenm == "." or filenm == "-":
                        self.lister.export_ly(markbit, self.project_dir / "{}.ly".format(mark.get("title","export"), title=mark.get("title","Untitled")))
                    else:
                        self.lister.export_ly(markbit, self.project_dir / filenm)
                self.display_list()
            elif ch == "^R" or ch == "^L" or ch == ascii.FF or ch == ascii.DC2:
                self.display_list()

            if line < 0:
                line = len(self.lister.get_order()) - 1
            elif line >= len(self.lister.get_order()):
                line = 0

    def _jam(self, stdscr):
        stdscr.keypad(True)
        stdscr.scrollok(True)

        self.stdscr = stdscr
        ch = stdscr.getkey()
        command = self.keymap.get(ch)
        self.cmdrecorder.add("mark_good")
        first_preset = "preset_0"
        self.commands.execute(first_preset, ui=self)
        self.cmdrecorder.add(first_preset)

        while command != "quit":
            if command is not None:
                self.cmdrecorder.add(command)
                self.commands.execute(command, ui=self)
            else:
                self.putln("Unknown key: '{}' (len:{})".format(ch, len(ch)))
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


