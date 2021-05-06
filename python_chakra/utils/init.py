from ctypes import CDLL
from os import name

__all__ = 'chakra_core',
if name == "nt":
    chakra_core = CDLL("./ChakraCore.dll")
elif name == "posix":
    chakra_core = CDLL("./libChakraCore.dylib")
