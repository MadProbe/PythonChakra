from ctypes import *
from dll_wrapper import *
from fifo_queue import FIFOQueue


__all__ = "PromiseFIFOQueue",


class PromiseFIFOQueue(FIFOQueue):
    def run(self, task):
        try:
            result = JSValueRef()
            arguments = pointer(js_undefined)
            chakra_core.JsCallFunction(c_void_p(task),
                                       arguments, 1, byref(result))
        except Exception as ex:
            print(
                "An error happed when executed promise continuation callback:", ex, sep="\n")
        finally:
            js_release(c_void_p(task))
