from index import *
import sys
import simple_chalk

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
        print(simple_chalk.chalk.yellow("[WARN]"), *map(js_value_to_string, args))

    @javascript_method()
    def error(*args, **_):
        print(simple_chalk.chalk.red("[ERROR]"), *map(js_value_to_string, args), file=sys.stderr)
    
    @javascript_method()
    def write_(*args, **_):
        print(*map(js_value_to_string, args), end=None)
    global_this["writeln"] = create_function(log, "log", attach_to_global_as="print", attach_to=console)
    create_function(warn, "warn", attach_to=console)
    create_function(error, "error", attach_to=console)
    create_function(write_, "write", attach_to_global_as=True)
    
    runtime.exec_module("./test.js")
