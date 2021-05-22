import sys

from python_chakra import *
from simple_chalk import chalk

with JSRuntime() as (runtime, global_this):
    true = runtime.get_true()
    global_this["__from_wrapper__"] = true
    console = Object(attach_to_global_as="console")
    console["WIP"] = true

    @jsfunc(attach_to_global_as=("print", "writeln"), attach_to=console)
    def log(*args, **_):
        print(*map(js_value_to_string, args))

    @jsfunc(attach_to=console)
    def warn(*args, **_):
        args = map(js_value_to_string, args)
        print(chalk.yellow("[WARN]"), *args)

    @jsfunc(attach_to=console)
    def error(*args, **_):
        args = map(js_value_to_string, args)
        print(chalk.red("[ERROR]"), *args, file=sys.stderr)

    @jsfunc(attach_to_global_as=True)
    def write(*args, **_):
        print(*map(js_value_to_string, args), end=None)

    @jsfunc(attach_to_global_as=True)
    def count(a: JSValueRef = None, b: JSValueRef = None, **_):
        return Number(a) + Number(b)

    runtime.exec_module("./examples/test.js")
