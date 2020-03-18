#!/usr/bin/env python
import os

from fabric.main import main as _main


def main():
    _main([os.path.join(os.path.dirname(__file__), 'fabfile.py')])
