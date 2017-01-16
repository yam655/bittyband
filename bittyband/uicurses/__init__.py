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
import threading
import queue
import sys
import select

from .genericlister import GenericLister
from .jam import JamScreen
from .simpleplay import SimplePlay


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

    def _terminate(self, stdscr):
        self.running = False
        if interrupt_main is None:
            stdscr.clear()
            stdscr.puts("Press any key to quit.")
        else:
            interrupt_main()

    def wire(self, **wiring):
        self.wiring = wiring

    def _start(self, generator, logic=None):
        curses.wrapper(self._start_up, generator, logic)

    def _start_up(self, stdscr, generator, logic):
        self.logic_thread = threading.Thread(target=self._switch(stdscr, generator, logic), daemon=True)
        self.logic_thread.run()
        self._getch_watcher(stdscr)

    def start_jam(self):
        return curses.wrapper(self.switch_jam)

    def _getch_watcher(self, stdscr):
        while self.running:
            select.select([sys.stdin], [], [])
            key = stdscr.getkey()
            self._getch_queue.put(key)

    def get_key(self, block=True, timeout=None):
        if timeout:
            check = select.select([sys.stdin], [], [], timeout)[0]
            if len(check) == 0:
                return None
            # curses.halfdelay(timeout)
            # try:
            ret = self.stdscrs[-1].getkey()
                # if ret == curses.ERR:
                #     ret = None
            # except:
            #     ret = None
            # finally:
            #     curses.nocbreak()
            #     curses.cbreak()
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
        return ret

    def _switch(self, stdscr, generator, logic=None):
        self.stdscrs.append(stdscr)
        # if self._getch_thread is None:
        #     self._getch_thread = threading.Thread(target=self._getch_watcher, daemon=True, args=(stdscr,))
        #     self._getch_thread.run()
        item = generator(self.config)
        item.wire(logic=logic, **self.wiring)
        ret = item(stdscr)
        del self.stdscrs[-1]
        # if len(self.stdscrs) == 0:
        #     self._terminate(stdscr)
        return ret

    def switch_jam(self, stdscr):
        return self._switch(stdscr, JamScreen)

    def start_list(self):
        return curses.wrapper(self.switch_list)

    def switch_list(self, stdscr):
        return self._switch(stdscr, GenericLister, logic="jam_lister")

    def start_import(self):
        return curses.wrapper(self.switch_import)
        # self._start(GenericLister, logic="import_lister")

    def switch_import(self, stdscr):
        return self._switch(stdscr, GenericLister, logic="import_lister")

    def play_ui(self, callback, *, seek=None):
        p = SimplePlay(self.config)
        p.wire(seek=seek, **self.wiring)
        p(self.stdscrs[-1], callback)

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
