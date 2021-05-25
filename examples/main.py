import sys

from python_chakra import *
from simple_chalk import chalk


print("Start")


with JSRuntime() as (runtime, global_this):
    true = runtime.get_true()
    false = runtime.get_false()
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
    def count(a: JSValueRef = None, b: JSValueRef = None, *_, **_2):
        return Number(a) + Number(b)

    @jsfunc(attach_to=Reflect)
    def isCallable(value: JSValueRef = None, *_, **_2):
        return true if value is not None and \
            Reflect.is_callable(value) else false

    @jsfunc(attach_to=Reflect)
    def isConstructor(value: JSValueRef = None, *_, **_2):
        return true if value is not None and \
            Reflect.is_constructor(value) else false

    runtime.exec_module("./examples/test.js")
