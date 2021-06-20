import asyncio
import sys

from python_chakra import *
from simple_chalk import chalk


print("Start")


global_this["__from_wrapper__"] = true
console = Object(attach_to_global_as="console")


@jsfunc(attach_to_global_as=("print", "writeln"), attach_to=console)
def log(*args):
    print(*map(js_value_to_string, args))


@jsfunc(attach_to=console)
def warn(*args):
    args = map(js_value_to_string, args)
    print(chalk.yellow("[WARN]"), *args)


@jsfunc(attach_to=console)
def error(*args):
    args = map(js_value_to_string, args)
    print(chalk.red("[ERROR]"), *args, file=sys.stderr)


@jsfunc(attach_to_global_as=True)
def write(*args):
    print(*map(js_value_to_string, args), end=None)


@jsfunc(attach_to_global_as=True)
def sum(a, b):
    return Number(a) + Number(b)


@jsfunc(attach_to=Reflect, fill_value=undefined)
def isCallable(value):
    return Reflect.is_callable(value)


@jsfunc(attach_to=Reflect, fill_value=undefined)
def isConstructor(value):
    return Reflect.is_constructor(value)


@jsfunc(attach_to_global_as=True)
async def sleep(value=0):
    await asyncio.sleep(float(Number(value)))


with JSRuntime() as runtime:
    runtime.exec_module("./examples/tests/__all__.js")
