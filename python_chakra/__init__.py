import sys

assert sys.version_info >= (3, 7), \
    "Only versions of C Python interpreter greater than or equal to 3.7 are supported"

from .index import *  # noqa: F401, E402

__title__ = "python_chakra"
__author__ = "MadProbe"
__licence__ = "MIT"
__copyright__ = "Copyright 2021 - present MadProbe"
__version__ = "0.0.1"
