from __future__ import annotations

from asyncio import Event
from collections import UserString
from collections.abc import MutableSequence
from math import ceil, floor, trunc
from numbers import Number as _Number
from os import getcwd
from sys import maxsize
from traceback import format_exception
from typing import Any, Awaitable, Optional, Tuple, Union

from .dll_wrapper import *
from .modules import (JavaScriptModule, ModuleRuntime, default_loader,
                      default_path_resolver)
from .utils import ValueSkeleton


def jsfunc(fname=None, *, constructor=False,
           attach_to_global_as: GlobalAttachments = None,
           attach_to_as: Optional[str] = None,
           attach_to: Optional[JSValueRef] = None,
           wrap_returns: Optional[bool] = True):
    def wrapper(function):
        nonlocal attach_to, attach_to_as, attach_to_global_as
        name = fname if fname is not None else function.__name__

        @CFUNCTYPE(c_void_p, JSValueRef, c_bool,
                   POINTER(POINTER(JSValueRef)),
                   c_ushort, c_void_p)
        def dummy(callee, new_call, args, arg_count, _):
            if new_call and not constructor:
                throw(create_type_error(f"{name} is not a constructor"))
            else:
                try:
                    if arg_count == 0:
                        this = None
                    else:
                        this = args[0]
                    args = c_array_to_iterator(args, arg_count, 1)
                    r = function(*args, this=this, callee=callee,
                                 new_call=bool(new_call))
                    while r is not None and hasattr(r, "_as_parameter_"):
                        r = r._as_parameter_
                    if wrap_returns:
                        if r is True:
                            r = js_true
                        if r is False:
                            r = js_false
                        if type(r) is str:
                            r = str_to_js_string(r)
                    if type(r) is JSValueRef:
                        r = r.value
                    return r
                except Exception as ex:
                    message = format_exception(type(ex), ex, ex.__traceback__)
                    throw(create_error('\n'.join(message)))

        _frefs.append(dummy)
        function._as_parameter_ = create_function(dummy, name)
        if attach_to_global_as:
            if attach_to_global_as is True:
                if name is None:
                    raise TypeError
                attach_to_global_as = name
            if type(attach_to_global_as) is tuple:
                for prop in attach_to_global_as:
                    if prop is True:
                        if name is None:
                            raise TypeError
                        prop = name
                    set_property(js_globalThis, prop, function)
            else:
                set_property(js_globalThis, attach_to_global_as, function)
        if attach_to:
            if not attach_to_as:
                if name is None:
                    raise TypeError
                attach_to_as = name
            set_property(attach_to, attach_to_as, function)
        return function
    return wrapper


class Boolean(ValueSkeleton):
    __slots__ = "_as_parameter_",

    def __init__(self, value: JSValueRef) -> None:
        self._as_parameter_ = value

    def is_boolean(self):
        return True


class Object(ValueSkeleton):
    class Virtual:
        def __init__(self) -> None:
            pass
    __virtual__ = Virtual()

    def __init__(self, value: JSValueRef = None,
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

    def set_property(self, name: Union[str, int], value: JSValueRef):
        set_property(self, name, value)
        return self

    def get_property(self, name: Union[str, int]) -> JSValueRef:
        return get_property(self, name)

    def __getitem__(self, name: Union[str, int]) -> JSValueRef:
        return self.get_property(name)

    def __setitem__(self, name: Union[str, int], value: JSValueRef):
        return self.set_property(name, value)

    def is_object(self):
        return True


class Number(ValueSkeleton, _Number):
    __slots__ = "_as_parameter_", "value"
    _as_parameter_: JSValueRef
    value: float

    def __init__(self, value: NumberLike) -> None:
        if type(value) is Number:
            # Borrow properties from Number
            # for a small optimization (speed + memory)
            self._as_parameter_ = value._as_parameter_
            self.value = value.value
        else:
            self._as_parameter_ = to_number(value)
            self.value = to_double(value)

    def __update(self) -> Number:
        self._as_parameter_ = to_number(self.value)
        return self

    def as_integer_ratio(self) -> Tuple[int, int]:
        return self.value.as_integer_ratio()

    def is_number(self):
        return True

    def to_float(self) -> float:
        return self.value

    def __iadd__(self, other: NumberLike) -> Number:
        self.value += _to_float(other)
        return self.__update()

    def __isub__(self, other: NumberLike) -> Number:
        self.value -= _to_float(other)
        return self.__update()

    def __itruediv__(self, other: NumberLike) -> Number:
        self.value /= _to_float(other)
        return self.__update()

    def __ifloordiv__(self, other: NumberLike) -> Number:
        self.value //= _to_float(other)
        return self.__update()

    def __imul__(self, other: NumberLike) -> Number:
        self.value *= _to_float(other)
        return self.__update()

    def __imod__(self, other: NumberLike) -> Number:
        self.value %= _to_float(other)
        return self.__update()

    def __ipow__(self, other: NumberLike,
                 modulo: Optional[NumberLike] = None) -> Number:
        if modulo is not None:
            other = _to_float(other)
            modulo = _to_float(modulo)
            self.value = self.value ** other % modulo
        else:
            self.value **= _to_float(other)
        return self.__update()

    def __add__(self, other: NumberLike) -> Number:
        return Number(self).__iadd__(other)

    def __sub__(self, other: NumberLike) -> Number:
        return Number(self).__isub__(other)

    def __truediv__(self, other: NumberLike) -> Number:
        return Number(self).__itruediv__(other)

    def __floordiv__(self, other: NumberLike) -> Number:
        return Number(self).__ifloordiv__(other)

    def __divmod__(self, other: NumberLike) -> Tuple[Number, Number]:
        return (self // other, self % other)

    def __mod__(self, other: NumberLike) -> Number:
        return Number(self).__imod__(other)

    def __pow__(self, other: NumberLike,
                modulo: Optional[NumberLike] = None) -> Number:
        return Number(self).__ipow__(other, modulo)

    def __repr__(self) -> str:
        return f"Number(value={self.value})"

    def __eq__(self, other: NumberLike) -> bool:
        return self.value == _to_float(other)

    def __ne__(self, other: NumberLike) -> bool:
        return self.value != _to_float(other)

    def __gt__(self, other: NumberLike) -> bool:
        return self.value > _to_float(other)

    def __ge__(self, other: NumberLike) -> bool:
        return self.value >= _to_float(other)

    def __lt__(self, other: NumberLike) -> bool:
        return self.value < _to_float(other)

    def __le__(self, other: NumberLike) -> bool:
        return self.value <= _to_float(other)

    def __abs__(self) -> Number:
        return Number(abs(self.value))

    def __neg__(self) -> Number:
        return Number(-self.value)

    def __pos__(self) -> Number:
        return self

    def __bool__(self) -> bool:
        return self.value != 0.0

    def __float__(self) -> float:
        return float(self.value)

    def __int__(self) -> int:
        return int(self.value)

    def __index__(self) -> int:
        return int(self.value)

    def __len__(self) -> int:
        return max(min(len(str(self.value)), 0), maxsize)

    def __iter__(self) -> Iterable[Optional[int]]:
        for digit_or_dot in str(self.value):
            if digit_or_dot == ".":
                yield None
            else:
                yield int(digit_or_dot)

    def __ceil__(self) -> int:
        return ceil(self.value)

    def __floor__(self) -> int:
        return floor(self.value)

    def __trunc__(self) -> int:
        return trunc(self.value)

    def __round__(self, ndigits: Optional[int] = None) -> int:
        return round(self.value, ndigits)


class String(ValueSkeleton, UserString):
    data: str
    _as_parameter_: JSValueRef
    __slots__ = "data", "_as_parameter_"

    def __init__(self, seq) -> None:
        if type(seq) is POINTER(JSValueRef):
            seq = seq[0]
        if type(seq) is JSValueRef:
            seq = js_value_to_string(seq)
        super().__init__(seq)
        self._as_parameter_ = str_to_js_string(self.data)


class Function(Object):
    def __init__(self) -> None:
        pass

    def is_function(self):
        return True

    def __call__(self, *args: Any, **kwds: Any) -> Any:
        return call(self, *args, **kwds)


class Promise(Object, Awaitable):
    def __init__(self, F) -> None:
        promise, resolve, reject = create_promise()
        super().__init__(promise)
        F(resolve, reject)

    def is_promise(self):
        return True

    async def __wait__(self):
        event = Event()
        value = None

        @jsfunc()
        def callback(val, **_2):
            nonlocal value
            event.set()
            value = val

        call(Fridge["Promise"]["prototype"]["then"](), callback, this=self)
        await event.wait()

        return value

    def __await__(self):
        return self.__wait__().__await__()


class Array(Object, MutableSequence):
    def __init__(self) -> None:
        pass

    def is_array(self):
        return True


class LogicalError(Exception):
    pass


class NotConstructableError(Exception):
    """
    Indicates that class is not constructable
    """
    pass


class Reflect():
    _as_parameter_ = js_reflect

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
_frefs = []
NumberLike = Union[Number, JSValueRef, int, float]
_True = Literal[True]
GlobalAttachments = Union[Tuple[Union[str, _True], ...], str, _True, None]


def _to_float(other: NumberLike) -> float:
    if type(other) is float:
        return other
    elif type(other) is Number:
        return other.value
    elif type(other) is JSValueRef:
        return to_double(other)
    else:
        return float(other)


_runtime: c_void_p = None


class JSRuntime:
    __slots__ = "_as_parameter_", "__flags", "__runtime", \
                "__context", "__module_runtime", "__promise_queue"

    def __init__(self, *, flags: int = 0x22):
        global _runtime
        if _runtime:
            raise LogicalError("A runtime is already created!")
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
        self.__promise_queue.append(c_void_p(task))

    def memory_limit(self, limit: int = None) -> Optional[int]:
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
        global _runtime
        self.__runtime = create_runtime(self.__flags)
        self._as_parameter_ = self.__runtime
        _runtime = self.__runtime
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
        global _runtime, _frefs
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
            print("Failed to dispose object references")
        _frefs.clear()
        try:
            set_current_context(0)
            dispose_runtime(self)
        except:  # noqa: E722
            print("Failed to dispose runtime")
        # else:
            # print("P")
        self.__runtime = None
        _runtime = None
        self.__context = None
        self._as_parameter_ = None
