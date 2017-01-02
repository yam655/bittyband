#!/bin/env python3

__author__ = "S.W. Black"
__all__ = ["app","parse"]

from .config import parse
from .app import app

def main(argv):
    app(parse(argv))

