#!/usr/bin/env python

__major__ = 0
__minor__ = 1
__release__ = 0
__dotbranch__ = (__major__, __minor__,)
__branch__ = '.'.join(['{}'.format(_) for _ in __dotbranch__])
__dotversion__ = (__major__, __minor__, __release__,)
__version__ = '.'.join(['{}'.format(_) for _ in __dotversion__])
__desc__ = 'A rolling restart framework for distributed databases'
