from ctypes import CDLL
from os import name
from os.path import dirname

__all__ = 'chakra_core',
if name == "nt":
    chakra_core = CDLL(f"{dirname(__file__)}/libs/ChakraCore.dll")
elif name == "posix":
    chakra_core = CDLL(f"{dirname(__file__)}/libs/libChakraCore.dylib")
