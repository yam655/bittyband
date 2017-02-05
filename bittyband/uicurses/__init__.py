#!/usr/bin/env python3

try:
    import curses
except ImportError:
    curses = None

try:
    from _thread import interrupt_main
except ImportError:
    interrupt_main = None

from pathlib import Path
import locale
import queue
import sys
import select

from .genericlister import GenericLister
from .jam import JamScreen
from .simpleplay import SimplePlay
from .spreader import Spreader


locale.setlocale(locale.LC_ALL, '')
code = locale.getpreferredencoding()

def is_available():
    return curses is not None


class UiCurses:

    def __init__(self, config):
        self.project_dir = Path(config["instance"]["project_dir"])
        self.config = config
        self.wiring = {}
        self.stdscrs = []
        self._getch_queue = queue.Queue()
        self._getch_thread = None
        self.running = True
        self.help = None

    def wire(self, **wiring):
        self.help = wiring.get("help")
        self.wiring = wiring

    def get_key(self, block=True, timeout=None):
        if timeout:
            check = select.select([sys.stdin], [], [], timeout)[0]
            if len(check) == 0:
                return None
            ret = self.stdscrs[-1].getkey()
        elif block:
            ret = self.stdscrs[-1].getkey()
        else:
            self.stdscrs[-1].nodelay(1)
            try:
                ret = self.stdscrs[-1].getkey()
                if ret == curses.ERR:
                    ret = None
            except:
                ret = None
            finally:
                self.stdscrs[-1].nodelay(0)
        if len(ret) == 1:
            if ord(ret) < 0x20:
                ret = "^{}".format(chr(ord(ret) + ord('@')))
            elif ord(ret) == 0x7f:
                ret = "^?"
        return ret

    def _switch(self, stdscr, generator, *, logic=None, args=()):
        self.stdscrs.append(stdscr)
        item = generator(self.config)
        if hasattr(item, "wire"):
            item.wire(logic=logic, **self.wiring)
        ret = item(stdscr, args=args)
        del self.stdscrs[-1]
        return ret

    def start_jam(self):
        return curses.wrapper(self.switch_jam)

    def switch_jam(self, stdscr):
        return self._switch(stdscr, JamScreen)

    def start_list(self):
        return curses.wrapper(self.switch_list)

    def switch_list(self, stdscr):
        return self._switch(stdscr, GenericLister, logic="jam_lister")

    def start_import(self):
        return curses.wrapper(self.switch_import)

    def switch_import(self, stdscr):
        return self._switch(stdscr, GenericLister, logic="import_lister")

    def start_import_file(self):
        return curses.wrapper(self.switch_import_file)

    def switch_import_file(self, stdscr = None):
        if stdscr is None and len(self.stdscrs) > 0:
            stdscr = self.stdscrs[-1]
        ret = self._switch(stdscr, Spreader, logic="importer")
        if len(self.stdscrs) > 0:
            # curses.ungetch(ord("L") - ord("@"))
            curses.ungetch("Q")
        return ret

    def show_help(self, txt, *, stdscr = None):
        if self.help is None:
            return "Help isn't available on this system."
        if stdscr is None and len(self.stdscrs) > 0:
            stdscr = self.stdscrs[-1]
        ret = self._switch(stdscr, GenericLister, logic="help", args=(txt,))
        return ret

    def play_ui(self, callback, *, seek=None):
        p = SimplePlay(self.config)
        p.wire(seek=seek, **self.wiring)
        p(self.stdscrs[-1], callback)

    def puts(self, something):
        stdscr = self.stdscrs[-1]
        max_x = stdscr.getmaxyx()[1]
        x = stdscr.getyx()[1]
        if x + len(something) >= max_x:
            stdscr.addstr("\n")
        stdscr.addstr(something)
        stdscr.refresh()

    def putln(self, something):
        stdscr = self.stdscrs[-1]
        stdscr.addstr(something)
        stdscr.addstr("\n")
        stdscr.refresh()
