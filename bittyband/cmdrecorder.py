#!/usr/bin/env python3

import queue
from pathlib import Path
import threading
from datetime import datetime, timedelta 

import sys

FILE_ID = "#,audio/x-vnd.mrbeany.record : v1 : "

class CommandRecorder:
    """ Internal Command Recorder (for jam mode) """
    def __init__(self, config, project_dir):
        self.fname = find_next_name(Path(project_dir), "cmd-{}.stream.txt")
        self.queue = queue.Queue() 
        self.thread = None

    def open(self):
        self.thread = threading.Thread(target=self.writer)
        self.thread.start()

    def writer(self):
        with open(self.fname, "at") as out:
            out.write(" : {}\n".format(strftime("%Y-%m-%dT%H:%M:%SZ", gmtime())))
            while True:
                item = self.queue.get()
                if item is None:
                    break
                out.write(item)
                out.write("\n")

    def close(self):
        if self.queue is not None and self.thread is not None:
            self.queue.join()
            self.queue.put(None)

    def find_next_name(self, project_dir, basenm):
        tme = str(time.time())
        t = project_dir / basenm.format(tme)
        idx = 1
        while t.exists():
            tme2 = tme + "." + str(idx)
            t = t.with_name(basenm.format(tme))
        t.write_text(FILE_ID)
        return str(t)

    def add(self, what):
        self.queue.put("{}\t{}".format(perf_counter(),ch))

    def __del__(self):
        self.close()

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
                global queues
                queues.conductor.put((t, v))
            line = sys.stdin.readline()
            line=line[:-1]

