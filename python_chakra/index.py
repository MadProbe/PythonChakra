from os import getcwd
from typing import Any, Union
from .dll_wrapper import *
from .modules import (JavaScriptModule, ModuleRuntime,
                      default_loader, default_path_resolver)
from .utils import ValueSkeleton


# Forwards
class Object:
    pass


class BigInt:
    pass


class Boolean(ValueSkeleton):
    __slots__ = "_as_parameter_",

    def __init__(self, value: JSValueRef) -> None:
        self._as_parameter_ = value

    def is_boolean(self):
        return True


class Object(ValueSkeleton):
    def __init__(self, /, *, value: JSValueRef = None,
                 attach_to_global_as: str = None) -> None:
        if value is None:
            value = create_object()
        self._as_parameter_ = value
        add_ref(self)
        _refs.append(self)
        if attach_to_global_as is not None:
            if type(attach_to_global_as) is not str:
                raise TypeError()
            set_property(js_globalThis, attach_to_global_as, self)

    def set_property(self, name: Union[str, int], value: JSValueRef, /) -> Object:
        set_property(self, name, value)
        return self

    def get_property(self, name: Union[str, int], /) -> JSValueRef:
        return get_property(self, name)

    def __getitem__(self, name: Union[str, int], /) -> JSValueRef:
        return self.get_property(name)

    def __setitem__(self, name: Union[str, int], value: JSValueRef, /) -> Object:
        return self.set_property(name, value)

    def is_object(self):
        return True


class Number(ValueSkeleton):
    def __init__(self) -> None:
        pass


class String(ValueSkeleton):
    def __init__(self) -> None:
        pass


class Function(Object):
    def __init__(self) -> None:
        pass

    def is_function(self):
        return True

    class Wrap:
        __slots__ = "__function",

        def __init__(self, function) -> None:
            self.__function = function

        def __call__(self, *args: Any, **kwds: Any) -> Any:
            pass


class Promise(Object):
    def __init__(self) -> None:
        pass

    def is_promise(self):
        return True

    def __await__(self):
        pass


class Array(Object):
    def __init__(self) -> None:
        pass

    def is_array(self):
        return True


class NotConstructableError(Exception):
    """
    Indicates that class is not constructable
    """
    pass


class Reflect():
    def __init__(self) -> None:
        raise NotConstructableError

    @staticmethod
    def is_array(value: JSValueRef) -> bool:
        return typeof(value) == js_types["array"]

    @staticmethod
    def is_boolean(value: JSValueRef) -> bool:
        return typeof(value) == js_types["boolean"]

    @staticmethod
    def is_callable(value: JSValueRef) -> bool:
        return is_callable(value)

    @staticmethod
    def is_constructor(value: JSValueRef) -> bool:
        return is_constructor(value)


class BigInt(ValueSkeleton):
    __slots__ = "__ints__", "_as_parameter_"

    def __init__(self, *ints: int) -> None:
        # they are list of uint32_t
        self.__ints__ = list(ints)

    def as_list(self):
        return list(self.__ints__)

    @staticmethod
    def from_value():
        pass

    def __update_bigint__(self):
        self._as_parameter_ = call()

    def __iadd__(self, other_bigint: BigInt) -> BigInt:
        other_ints = other_bigint.__ints__
        length = self.__ints__.__len__()
        for i in range(0, length):
            self.__ints__[i] = self.__ints__ + other_ints[i]
            overhead = self.__ints__[i] & 0xffffffff00000000
            if overhead != 0:
                if i + 1 < length:
                    self.__ints__[i] = self.__ints__ + overhead >> 32
                else:
                    self.__ints__.append(overhead >> 32)

    def is_bigint(self):
        return True


class Undefined(ValueSkeleton):
    def __init__(self) -> None:
        self._as_parameter_ = js_undefined

    def is_undefined(self):
        return True


class Null(ValueSkeleton):
    def __init__(self) -> None:
        self._as_parameter_ = js_null

    def is_null(self):
        return True


_refs = []


class JSRuntime:
    __slots__ = "_as_parameter_", "__flags", "__runtime", \
                "__context", "__module_runtime", "__promise_queue"

    def __init__(self, /, *, flags: int = 0x22):
        self.__flags = flags
        self.__runtime = c_void_p()
        self.__context = c_void_p()
        self.__promise_queue = PromiseFIFOQueue()
        self.__module_runtime = ModuleRuntime(self, self.__promise_queue)
        self._as_parameter_ = None

    def exec_module(self, specifier: str):
        module_runtime = self.__module_runtime
        spec = module_runtime.path_resolver(default_path_resolver,
                                            self.__get_base(),
                                            specifier)
        code = module_runtime.loader(default_loader, spec)
        module = JavaScriptModule(self.__promise_queue,
                                  module_runtime.queue,
                                  spec, code, None, True)
        module_runtime.add_module(str(spec), module)
        module.parse()

    def __get_base(self):
        return "file://" + getcwd() + "/"

    def exec_script(self, specifier: str, async_: bool = True):
        fileurl = default_path_resolver(None, self.__get_base(), specifier)
        script = default_loader(None, fileurl)
        if async_:
            script = f"(async()=>{{{script}}})()"
        script = create_string_buffer(script.encode("UTF-16"))
        buffer = create_external_array_buffer(script)
        run_script(buffer, create_c_string(str(fileurl)))
        self.__promise_queue.exec()

    def get_true(_):
        return Boolean(js_true)

    def get_false(_):
        return Boolean(js_false)

    def get_null(_):
        return Null()

    def get_undefined(_):
        return Undefined()

    def __queue_promise(self, task):
        # print("__queue_promise")
        add_ref(c_void_p(task))
        self.__promise_queue.append(task)

    def memory_limit(self, limit: int = None) -> Union[int, None]:
        if limit is None:
            return get_runtime_memory_limit(self)
        else:
            set_runtime_memory_limit(self, limit)

    def memory_usage(self) -> int:
        return get_runtime_memory_usage(self)

    def exit_and_reenter(self):
        self.__exit__()
        return self.__enter__()

    def __enter__(self):
        self.__runtime = create_runtime(self.__flags)
        self._as_parameter_ = self.__runtime
        self.__context = create_context(self)
        set_current_context(self.__context)
        init_utilitites()
        init_other_utilities()

        @CFUNCTYPE(c_void_p, JSValueRef, c_void_p)
        def promise_continuation_callback(task, user_data):
            self.__queue_promise(task)

        @CFUNCTYPE(c_void_p, JSValueRef, JSValueRef, c_bool, c_void_p)
        def promise_rejections_callback(promise, reason, handled, _):
            if not handled:
                print("Unhandled promise rejection:",
                      js_value_to_string(c_void_p(reason)))
        set_promise_callback(promise_continuation_callback)
        set_rejections_callback(promise_rejections_callback)
        self.__module_runtime.attach_callcacks()

        return self, Object(value=js_globalThis)

    def __exit__(self, *_):
        try:
            module: JavaScriptModule
            for module in self.__module_runtime.modules.values():
                module.dispose()
            self.__module_runtime.modules.clear()
        except:  # noqa: E722
            print("Failed to dispose modules")
        try:
            for ref in _refs:
                js_release(ref)
        except:  # noqa: E722
            print("Failed to dispose ref")
        try:
            set_current_context(0)
            dispose_runtime(self)
        except:  # noqa: E722
            print("Failed to dispose runtime")
        # else:
            # print("P")
        self.__runtime = None
        self.__context = None
        self._as_parameter_ = None
