import sys
from simple_chalk import chalk
from index import *

with JSRuntime() as (runtime, global_this):
    true = runtime.get_true()
    global_this["__from_wrapper__"] = true
    console = Object(attach_to_global_as="console")
    console["WIP"] = true

    @javascript_method()
    def log(*args, **_):
        print(*map(js_value_to_string, args))

    @javascript_method()
    def warn(*args, **_):
        args = map(js_value_to_string, args)
        print(chalk.yellow("[WARN]"), *args)

    @javascript_method()
    def error(*args, **_):
        args = map(js_value_to_string, args)
        print(chalk.red("[ERROR]"), *args, file=sys.stderr)

    @javascript_method()
    def write_(*args, **_):
        print(*map(js_value_to_string, args), end=None)
    global_this["writeln"] = create_function(log, "log",
                                             attach_to_global_as="print",
                                             attach_to=console)
    create_function(warn, "warn", attach_to=console)
    create_function(error, "error", attach_to=console)
    create_function(write_, "write", attach_to_global_as=True)

    runtime.exec_module("./test.js")
