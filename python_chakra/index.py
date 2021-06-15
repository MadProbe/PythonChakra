from __future__ import annotations

from asyncio import Event
from asyncio.events import get_event_loop
from collections import UserString
from collections.abc import MutableSequence
from inspect import iscoroutinefunction
from math import ceil, floor, trunc
from numbers import Number as _Number
from os import getcwd
from sys import maxsize
from traceback import format_exception
from typing import Any, AsyncGenerator, Awaitable, Callable, Dict, Generator, \
    Optional, Tuple, TypeVar, Union, overload

from .dll_wrapper import *
from .modules import JSModule, ModuleRuntime, default_loader, \
    default_path_resolver
from .utils import BaseValue


_T = TypeVar("_T")


class Boolean(BaseValue):
    _as_parameter_ = Fridge["Boolean"]()
    __slots__ = ()

    def __init__(self, value: JSValueRef) -> None:
        self._as_parameter_ = value

    def is_boolean(self):
        return True


class Object(BaseValue, SupportsLazyInit):
    class __PropDesc__:
        value: Optional[JSValueRef]
        get: Optional[JSValueRef]
        set: Optional[JSValueRef]
        writable: bool
        enumerable: bool
        configurable: bool
        __slots__ = "value", "get", "set", "writable", "enumerable", \
            "configurable"

        def __init__(self,
                     value: Optional[JSValueRef],
                     get: Optional[JSValueRef],
                     set: Optional[JSValueRef],
                     writable: bool,
                     enumerable: bool,
                     configurable: bool) -> None:
            self.value = value
            self.get = get
            self.set = set
            self.writable = writable
            self.configurable = configurable
            self.enumerable = enumerable

    class __Lazy__:
        __properties: Dict[Union[str, int], Object.__PropDesc__]
        _attach_to_global_as: str
        __slots__ = "__properties", "_attach_to_global_as"

        def __init__(self, _) -> None:
            self.__properties = dict()
            self._attach_to_global_as = _

        def define_property(self, name: str, value: JSValueRef,
                            get: JSValueRef = None, set: JSValueRef = None,
                            writable: bool = True, enumerable: bool = True,
                            configurable: bool = True) -> None:
            desc = Object.__PropDesc__(value, get, set, writable,
                                       enumerable, configurable)
            self.__properties[name] = desc

        def delete_property(self, name) -> None:
            del self.__properties[name]

        def __setitem__(self, name, value) -> None:
            if name in self.__properties.keys():
                if self.__properties[name].writable:
                    self.__properties[name].value = value
                else:
                    raise TypeError
            else:
                self.define_property(name, value, None, None, True, True, True)

        def __getitem__(self, name) -> Any:
            return self.__properties[name].value

        def __delitem__(self, name) -> None:
            self.delete_property(name)

        def __iter__(self) -> Generator[Tuple[Union[str, int],
                                        Object.__PropDesc__], None, None]:
            return zip(self.__properties.keys(),
                       self.__properties.values())

    __lazy__: __Lazy__
    __initialized__: bool
    _as_parameter_: JSValueRef = Fridge["Object"]()
    __slots__ = "__lazy__", "__initialized__"

    def __init__(self, value: JSValueRef = None, *,
                 attach_to_global_as: str = None) -> None:
        global _runtime, _refs
        if _runtime is not None:
            if value is None:
                value = create_object()
            self.__initialized__ = True
            self._as_parameter_ = value
            add_ref(self)
            _refs.append(self)
            if attach_to_global_as is not None:
                if type(attach_to_global_as) is not str:
                    raise TypeError()
                global_this[attach_to_global_as] = self
        else:
            self.__initialized__ = False
            if hasattr(value, "_as_parameter_") or type(value) is JSValueRef:
                self._as_parameter_ = value
            else:
                self._as_parameter_ = None
            _refs.append(self)
            self.__lazy__ = Object.__Lazy__(attach_to_global_as)
            lazy_object_queue.append(self)

    def set_property(self, name: Union[str, int], value: JSValueRef) -> Object:
        if self.__initialized__:
            set_property(self, name, value)
        else:
            self.__lazy__[name] = value
        return self

    def get_property(self, name: Union[str, int]) -> JSValueRef:
        if not self.__initialized__:
            return self.__lazy__[name]
        return get_property(self, name)

    def __getitem__(self, name: Union[str, int]) -> JSValueRef:
        return self.get_property(name)

    def __setitem__(self, name: Union[str, int], value: JSValueRef) -> Object:
        return self.set_property(name, value)

    def __lazy_init__(self) -> None:
        if self._as_parameter_ is None:
            self._as_parameter_ = create_object()
        add_ref(self)
        self.__initialized__ = True
        for key, descriptor in self.__lazy__:
            self[key] = descriptor.value
        atga = self.__lazy__._attach_to_global_as
        if atga:
            global_this[atga] = self

    def is_object(self) -> Literal[True]:
        return True


def jsfunc(fname=None, *, constructor=False,
           attach_to_global_as: GlobalAttachments = None,
           attach_to_as: Optional[str] = None,
           attach_to: Optional[JSValueRef] = None,
           wrap_returns: Optional[bool] = True):
    def wrapper(function: _T) -> _T:
        nonlocal attach_to, attach_to_as, attach_to_global_as
        name = fname if fname is not None else function.__name__
        is_coro_func = iscoroutinefunction(function)

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
                    if is_coro_func:
                        promise, resolve, reject = create_promise()
                        kwargs = {"resolve": Function(resolve),
                                  "reject": Function(reject)}
                    else:
                        kwargs = _empty_dict
                    r = function(*args, this=this, callee=callee,
                                 new_call=bool(new_call), **kwargs)
                    if is_coro_func:
                        loop = get_event_loop()
                        r = loop.run_until_complete(r)
                    if wrap_returns:
                        if r is True:
                            r = js_true
                        if r is False:
                            r = js_false
                        if type(r) is str:
                            r = str_to_js_string(r)
                        if type(r) in (int, float):
                            r = to_double(r)
                        if r is None:
                            r = js_undefined
                    r = walk_asparam_chain(r)
                    if is_coro_func:
                        call(resolve, r.value)
                        return promise.value
                    if type(r) is JSValueRef:
                        r = r.value
                    return r
                except Exception as ex:
                    message = format_exception(type(ex), ex,
                                               ex.__traceback__)
                    error = create_error('\n'.join(message))
                    if is_coro_func:
                        call(reject, error)
                        return promise.value
                    else:
                        throw(error)

        _frefs.append(dummy)
        if _runtime is None:
            class _(SupportsLazyInit):
                def __lazy_init__(_):
                    function._as_parameter_ = create_function(dummy, name)

            lazy_function_queue.append(_())
        else:
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
                    global_this[prop] = function
            else:
                global_this[attach_to_global_as] = function
        if attach_to:
            if not attach_to_as:
                if name is None:
                    raise TypeError
                attach_to_as = name
            Object(attach_to)[attach_to_as] = function
        return function
    return wrapper


class Number(BaseValue, _Number):
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

    def is_number(self) -> Literal[True]:
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


class String(BaseValue, UserString):
    _as_parameter_: JSValueRef = Fridge["String"]()
    __slots__ = "data",

    def __init__(self, seq) -> None:
        if type(seq) is POINTER(JSValueRef):
            seq = seq[0]
        if type(seq) is JSValueRef:
            seq = js_value_to_string(seq)
        super().__init__(seq)
        self._as_parameter_ = str_to_js_string(self.data)


class Function(Object, Callable):
    _as_parameter_: JSValueRef = Fridge["Function"]()

    def __init__(self, f: JSValueRef) -> None:
        super().__init__(f)

    def is_function(self) -> Literal[True]:
        return True

    def __call__(self, *args: Any, **kwds: Any) -> Any:
        return call(self, *args, **kwds)


class Promise(Object, Awaitable):
    __slots__ = "__event",
    _as_parameter_: JSValueRef = Fridge["Promise"]()
    _event: Event

    @staticmethod
    def _run_coro_like(F, *args: Any, **kwargs: Dict[str, Any]):
        if iscoroutinefunction(F):
            loop = get_event_loop()
            r = loop.run_until_complete(F(*args, **kwargs))
        else:
            r = F(*args, **kwargs)
        return r

    @staticmethod
    def _resolve(value: JSValueRef) -> JSValueRef:
        return call(Fridge["Promise"]["resolve"](), value,
                    this=Fridge["Promise"]())

    @staticmethod
    def _reject(value: JSValueRef) -> JSValueRef:
        return call(Fridge["Promise"]["reject"](), value,
                    this=Fridge["Promise"]())

    @staticmethod
    def resolve(value: JSValueRef) -> Promise:
        return Promise(Promise._resolve(value))

    @staticmethod
    def reject(value: JSValueRef) -> Promise:
        return Promise(Promise._reject(value))

    @staticmethod
    def all(values: Iterable[JSValueRef]) -> Promise:
        """
        A spec-compliant implementation of Promise.all() JS built-in function
        """
        def handler(resolve, reject):
            vals = list(values)
            length = len(vals)
            result = list(vals)
            done = 0
            for i, value in enumerate(vals):
                p = Promise._resolve(value)

                def capture(p, i):
                    @jsfunc()
                    def handler(value, **_):
                        nonlocal done
                        result[i] = value
                        done += 1
                        if done == length:
                            resolve(Array(result))

                    call(Fridge["Promise"]["prototype"]["then"](),
                         handler, reject, this=p)

                capture(p, i)
        return Promise(handler)

    def all_async_gen(*args: Promise) -> AsyncGenerator[JSValueRef, None]:
        """
        This is more naive implementation of Promise.all() JS built-in function
        TODO: better naming?
        """
        return (await Promise.resolve(value) for value in args)

    @overload
    def __init__(self, promise: JSValueRef) -> None:
        ...

    def __init__(self, F: Callable) -> None:
        if type(F) is JSValueRef:
            super().__init__(Promise._resolve(F))
        else:
            promise, resolve, reject = create_promise()
            super().__init__(promise)
            Promise._run_coro_like(F, Function(resolve), Function(reject))

    def is_promise(self) -> Literal[True]:
        return True

    async def __wait__(self) -> JSValueRef:
        if not hasattr(self, "_event") or self._event.is_set():
            event = self._event if hasattr(self, "_event") else Event()
            event.clear()

            @jsfunc()
            def callback(_, **_2):
                event.set()

            call(Fridge["Promise"]["prototype"]["then"](), callback, this=self)
            self._event = event
        else:
            event = self._event

        await event.wait()

        state = get_promise_state(self)
        if state == js_promise_states["resolved"]:
            return get_promise_result(self)
        elif state == js_promise_states["rejected"]:
            raise get_promise_result(self)
        else:
            # This happens when somebody somehow
            # changes _as_parameter_ value :(
            raise RuntimeError

    def __await__(self) -> Generator[Any, None, JSValueRef]:
        return self.__wait__().__await__()


class Array(Object, MutableSequence):
    def __init__(self) -> None:
        pass

    def is_array(self) -> None:
        return True


class LogicalError(Exception):
    pass


class NotConstructableError(Exception):
    """
    Indicates that class is not constructable
    """
    pass


class Reflect():
    _as_parameter_: JSValueRef = Fridge["Reflect"]()

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


class BigInt(BaseValue):
    __slots__ = "__ints__", "_as_parameter_"
    __ints__: List[int]
    _as_parameter_: JSValueRef

    def __init__(self, *ints: int) -> None:
        # they are list of uint32_t
        self.__ints__ = list(ints)

    def as_list(self) -> List[int]:
        return list(self.__ints__)

    def __update_bigint__(self) -> None:
        ints = str_to_js_string(''.join(self.__ints__))
        self._as_parameter_ = call(Fridge["BigInt"](), ints)

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

    def is_bigint(self) -> Literal[True]:
        return True


class Undefined(BaseValue):
    _as_parameter_: JSValueRef = js_undefined

    def is_undefined(self) -> Literal[True]:
        return True


class Null(BaseValue):
    _as_parameter_: JSValueRef = js_null

    def is_null(self) -> Literal[True]:
        return True


_refs = []
_frefs = []
_empty_dict = dict()
NumberLike = Union[Number, JSValueRef, int, float]
_True = Literal[True]
GlobalAttachments = Union[Tuple[Union[str, _True], ...], str, _True, None]
_runtime: JSRef = None
global_this = Object(js_globalThis)
Number._as_parameter_ = Fridge["Number"]()
true = Boolean(js_true)
false = Boolean(js_false)
undefined = Undefined()
null = Null()


def _to_float(other: NumberLike) -> float:
    if type(other) is float:
        return other
    elif type(other) is Number:
        return other.value
    elif type(other) is JSValueRef:
        return to_double(other)
    else:
        return float(other)


class JSRuntime:
    __slots__ = "_as_parameter_", "__flags", "__runtime", "__context", \
        "__module_runtime"
    __module_runtime: ModuleRuntime
    __runtime: Optional[JSRef]
    __context: Optional[JSRef]
    _as_parameter_: Optional[JSRef]
    flags: int

    def __init__(self, *, flags: int = 0x22):
        global _runtime
        if _runtime:
            raise LogicalError("A runtime is already created!")
        self.__flags = flags
        self.__runtime = JSRef()
        self.__context = JSRef()
        self.__module_runtime = ModuleRuntime(self)
        self._as_parameter_ = None
        promise_queue.clear()
        lazy_function_queue.append(Fridge)

    def exec_module(self, specifier: str):
        module_runtime = self.__module_runtime
        spec = module_runtime.path_resolver(default_path_resolver,
                                            self.__get_base(),
                                            specifier)
        code = module_runtime.loader(default_loader, spec)
        module = JSModule(spec, code, None, True)
        module_runtime.add_module(str(spec), module)
        module.parse()

    def __get_base(self):
        return "file://" + getcwd() + "/"

    def exec_script(self, specifier: str, async_: bool = True) -> None:
        fileurl = default_path_resolver(None, self.__get_base(), specifier)
        script = default_loader(None, fileurl)
        if async_:
            script = f"(async()=>{{{script}}})()"
        script = create_string_buffer(script.encode("UTF-16"))
        buffer = create_external_array_buffer(script)
        run_script(buffer, create_c_string(str(fileurl)))
        promise_queue.exec()

    def __queue_promise(self, task: JSValueRef) -> None:
        add_ref(task)
        promise_queue.append(task)

    def memory_limit(self, limit: int = None) -> Optional[int]:
        if limit is None:
            return get_runtime_memory_limit(self)
        else:
            set_runtime_memory_limit(self, limit)

    def memory_usage(self) -> int:
        return get_runtime_memory_usage(self)

    def exit_and_reenter(self) -> None:
        self.__exit__()
        return self.__enter__()

    def __enter__(self) -> JSRuntime:
        global _runtime
        self.__runtime = create_runtime(self.__flags)
        _runtime = self.__runtime
        self._as_parameter_ = _runtime
        self.__context = create_context(self)
        set_current_context(self.__context)

        @CFUNCTYPE(c_void_p, JSValueRef, c_void_p)
        def promise_continuation_callback(task, _) -> None:
            self.__queue_promise(JSValueRef(task))

        @CFUNCTYPE(c_void_p, JSValueRef, JSValueRef, c_bool, c_void_p)
        def promise_rejections_callback(promise, reason, handled, _) -> None:
            if not handled:
                print("Unhandled promise rejection:",
                      js_value_to_string(c_void_p(reason)))
        set_promise_callback(promise_continuation_callback)
        set_rejections_callback(promise_rejections_callback)
        self.__module_runtime.attach_callcacks()
        init_utilitites()
        init_other_utilities()

        return self

    def __exit__(self, *_: Any) -> None:
        global _runtime, _frefs
        try:
            for module in self.__module_runtime.modules.values():
                module.dispose()
            self.__module_runtime.modules.clear()
        except Exception as e:
            print("Failed to dispose modules, error:", e)
        try:
            for ref in _refs:
                walked: Optional[JSValueRef] = walk_asparam_chain(ref)
                if walked is not None and walked.value is not None:
                    js_release(ref)
        except Exception as e:
            print("Failed to dispose object references, error:", e)
        _frefs.clear()
        try:
            set_current_context(0)
            dispose_runtime(self)
        except Exception as e:
            print("Failed to dispose runtime, error:", e)
        self.__runtime = None
        _runtime = None
        self.__context = None
        self._as_parameter_ = None
