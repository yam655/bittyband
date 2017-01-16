#!/usr/bin/env python3

import time


class SimplePlay:
    ui = None
    seek = None

    def __init__(self, config):
        pass

    def wire(self, *, ui, seek=None, **kwargs):
        self.ui = ui
        self.seek = seek

    def __call__(self, stdscr, status):
        self.stdscr = stdscr
        y = self.stdscr.getmaxyx()[0]
        line = status()
        while line is not None:
            ch = self.ui.get_key(timeout=0.1)
            if ch is not None:
                if self.seek is None:
                    break
                if ch == 'q' or ch == 'Q' or ch == "^]":
                    break
                elif ch == '[' or ch == '{':
                    self.seek(-60)
                elif ch == ']' or ch == '}':
                    self.seek(60)
                elif ch == ',' or ch == '<':
                    self.seek(-1)
                elif ch == '.' or ch == '>':
                    self.seek(1)
            self.stdscr.addstr(y - 1, 0, str(line))
            self.stdscr.clrtoeol()
            self.stdscr.refresh()
            line = status()
            time.sleep(0.1)
