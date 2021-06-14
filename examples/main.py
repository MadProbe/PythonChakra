import asyncio
import sys

from python_chakra import *
from simple_chalk import chalk


print("Start")


global_this["__from_wrapper__"] = true
console = Object(attach_to_global_as="console")


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
def count(a=None, b=None, *_, **_2):
    return Number(a) + Number(b)


@jsfunc(attach_to=Reflect)
def isCallable(value=undefined, *_, **_2):
    return Reflect.is_callable(value)


@jsfunc(attach_to=Reflect)
def isConstructor(value=undefined, *_, **_2):
    return Reflect.is_constructor(value)


@jsfunc(attach_to_global_as=True)
def sleep(value=0, *_, **_2):
    async def f(resolve: Function, _: Function):
        await asyncio.sleep(float(Number(value)))
        resolve()
    return Promise(f)


with JSRuntime() as runtime:
    runtime.exec_module("./examples/tests/__all__.js")
