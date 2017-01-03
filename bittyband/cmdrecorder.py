#!/usr/bin/env python3

import queue
from pathlib import Path
import threading
from datetime import datetime, timedelta 
import time
from time import time,perf_counter

import sys

FILE_ID = "#,audio/vnd.mrbeany.bittyband.stream : v1\n"

class CommandRecorder:
    """ Internal Command Recorder (for jam mode) """
    def __init__(self, config):
        project_dir = Path(config["instance"]["project_dir"])
        self.fname = self.find_next_name(project_dir, "cmd-{}.stream.txt")
        self.queue = queue.Queue() 
        self.thread = None

    def start(self):
        self.thread = threading.Thread(target=self.writer)
        self.thread.start()

    def writer(self):
        global FILE_ID
        with open(self.fname, "wt") as out:
            out.write(FILE_ID)
            while True:
                if self.queue.empty():
                    out.flush()
                item = self.queue.get()
                if item is None:
                    break
                out.write(item)
                out.write("\n")
                self.queue.task_done()
        self.queue = None
        self.thread = None

    def end(self):
        if self.queue is not None and self.thread is not None:
            self.queue.join()
            self.queue.put(None)

    def find_next_name(self, project_dir, basenm):
        tme = str(time())
        t = project_dir / basenm.format(tme)
        idx = 1
        while t.exists():
            tme2 = tme + "." + str(idx)
            t = t.with_name(basenm.format(tme))
        t.write_text(FILE_ID)
        return str(t)

    def add(self, what):
        if self.queue is not None:
            self.queue.put("{},{}".format(perf_counter(),what))

    def __del__(self):
        if hasattr(self, "queue"):
            self.end()

    def read(self):
        line = sys.stdin.readline()
        if line.startswith("#!"):
            line = sys.stdin.readline()
        if line.startswith("#\t"):
            if not line.startswith(FILE_ID):
                sys.stderr.write("Unknown file format.\n")
                sys.exit(1)
            line = sys.stdin.readline() 
        line=line[:-1]
        lastEntry = 0
        while line != None and line != "":
            t = v = None
            try:
                (t,v) = line.split("\t")
            except:
                pass
            if len(v) == 1:
                v = ord(v)
            if t is not None:
                self.queue.put((t, v))
            line = sys.stdin.readline()
            line=line[:-1]

