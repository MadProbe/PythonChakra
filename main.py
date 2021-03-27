from index import *

with JSRuntime() as (runtime, global_this):
    true = runtime.get_true()
    global_this["__from_wrapper__"] = true
    console = Object()
    console["WIP"] = true
    global_this["console"] = console
    runtime.exec_module("./test.js")
