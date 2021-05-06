from ctypes import *
from dll_wrapper import *
from fifo_queue import FIFOQueue


__all__ = "PromiseFIFOQueue",
_ref = []


class PromiseFIFOQueue(FIFOQueue):
    def run(self, task):
        try:
            result = JSValueRef()
            arguments = pointer(js_undefined)
            _ref.append(arguments)
            # print(typeof(c_void_p(task)))
            chakra_core.JsCallFunction(c_void_p(task),
                                       arguments, 1, byref(result))
            # print("Done promise continuation callback")
        except Exception as ex:
            print("An error happed when executed promise continuation callback:",
                  ex, sep="\n")
        finally:
            js_release(c_void_p(task))
