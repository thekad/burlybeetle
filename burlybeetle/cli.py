#!/usr/bin/env python
import os

from fabric.main import main as _main


def main():
    # dirname(__file__) should always be the 'servo' package dir.
    # Tell Fabric's main() to explicitly use that fabfile path.
    _main([os.path.join(os.path.dirname(__file__), 'fabfile.py')])
