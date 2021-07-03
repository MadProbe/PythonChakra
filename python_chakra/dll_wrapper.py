from __future__ import annotations

import re
from abc import abstractmethod
from ctypes import *
from enum import IntEnum
from typing import Any, Dict, Generator, Iterable, List, Literal, Optional, \
    Protocol, Tuple, Union, runtime_checkable

from .utils import FIFOQueue, chakra_core


def walk_asparam_chain(value: Any) -> JSValueRef:
    while value is not None and hasattr(value, "_as_parameter_"):
        value = value._as_parameter_
    return value


@runtime_checkable
class SupportsLazyInit(Protocol):
    @abstractmethod
    def __lazy_init__() -> None:
        pass


class _LazyInitQueue(FIFOQueue[SupportsLazyInit]):
    def run(self, object: SupportsLazyInit) -> None:
        object.__lazy_init__()


lazy_function_queue = _LazyInitQueue()
lazy_object_queue = _LazyInitQueue()


class ErrorCodesEnum(IntEnum):
    OK = 0
    ErrorCategoryUsage = 0x10000
    ErrorInvalidArgument = 0x10001
    ErrorNullArgument = 0x10002
    ErrorNoCurrentContext = 0x10003
    ErrorInExceptionState = 0x10004
    ErrorNotImplemented = 0x10005
    ErrorWrongThread = 0x10006
    ErrorRuntimeInUse = 0x10007
    ErrorBadSerializedScript = 0x10008
    ErrorInDisabledState = 0x10009
    ErrorCannotDisableExecution = 0x1000a
    ErrorHeapEnumInProgress = 0x1000b
    ErrorArgumentNotObject = 0x1000c
    ErrorInProfileCallback = 0x1000d


class Fridge:
    """
    A frozen container for global objects
    """
    class __Dict__(dict):
        def __missing__(self, *_):
            raise ValueError

    class __ObjectEntry__:
        value: JSValueRef
        descendants: Dict[str, Fridge.__ObjectEntry__]
        __slots__ = "value", "descendants"

        def __init__(self, value, descendants) -> None:
            self.value = value
            self.descendants = descendants

    class __Lazy__(SupportsLazyInit):
        __store__: List[str]
        __pointer__: JSValueRef
        __slots__ = "__store__", "__pointer__"

        def __init__(self) -> None:
            self.__store__ = []

        def __getitem__(self, name) -> None:
            self.__store__.append(name)

        def __call__(self) -> Any:
            p = self.__pointer__ = JSValueRef()
            return p

        def __lazy_init__(self) -> None:
            for propname in self.__store__:
                Fridge[propname]
            if hasattr(self, "__pointer__"):
                self.__pointer__.value = Fridge().value
            else:
                raise UserWarning("When initializing value of built-in JS \
value, __pointer__ property was undefined. Did you forget to call Fridge \
class?")
            return self

    __this: __ObjectEntry__
    __current: __ObjectEntry__
    __initialized: bool = False
    __lazily_inited: List[__Lazy__] = []
    __current_lazy = __Lazy__()

    def __class_getitem__(cls, name):
        if cls.__initialized:
            cls.__current = cls.__current.descendants[name]
        else:
            cls.__current_lazy[name]
        return cls

    def __new__(cls) -> JSValueRef:
        if cls.__initialized:
            current = cls.__current.value
            cls.__current = cls.__this
        else:
            cls.__lazily_inited.append(cls.__current_lazy)
            current = cls.__current_lazy()
            cls.__current_lazy = Fridge.__Lazy__()
        return current

    @classmethod
    def __lazy_init__(cls):
        cls.scan()
        cls.__initialized = True
        for _lazily_inited in cls.__lazily_inited:
            _lazily_inited.__lazy_init__()

    @classmethod
    def scan(cls):
        d = dict()

        def _rec(obj: JSValueRef):
            def add(value):
                if typeof(value) not in (js_types["object"],
                                         js_types["function"]):
                    return
                if value.value in d:
                    entry = d.get(value.value)
                else:
                    _dict = Fridge.__Dict__()
                    entry = Fridge.__ObjectEntry__(value, _dict)
                    d[value.value] = entry
                    _dict.update(_rec(value).descendants)
                dict[name] = entry
            dict = Fridge.__Dict__()
            res = Fridge.__ObjectEntry__(obj, dict)
            d[obj.value] = res
            names = get_own_property_names(obj)
            length = to_double(get_property(names, "length"))
            for i in range(int(length)):
                name = get_property(names, i)
                name = js_value_to_string(name)
                try:
                    value: JSValueRef = get_property(obj, name)
                    add(value)
                except AssertionError:
                    get_exception()
            return res

        cls.__this = cls.__current = _rec(js_globalThis)


class PromiseFIFOQueue(FIFOQueue):
    _ref = []

    def run(self, task):
        try:
            result = JSValueRef()
            args = pointer(js_undefined)
            self._ref.append(args)
            chakra_core.JsCallFunction(task, args, 1, byref(result))
            self._ref.remove(args)
        except Exception as ex:
            print("An error happed when executed",
                  "promise continuation callback:", ex, sep="\n")
        finally:
            js_release(task)


promise_queue = PromiseFIFOQueue()
nullptr = POINTER(c_int)()
StrictModeType = Union[bool, Literal[0, 1]]
JSValueRef = c_void_p
JSRef = c_void_p
JSModuleRecord = c_void_p
_NumberLike = Union[POINTER(JSValueRef), JSValueRef, float, int]
PropertyDict = Dict[Union[str, int], JSValueRef]
c_func_type = chakra_core._FuncPtr
c_true = 1
c_false = 0
context_count = 1
js_types = {
    "undefined": 0,
    "null": 1,
    "number": 2,
    "string": 3,
    "boolean": 4,
    "object": 5,
    "function": 6,
    "error": 7,
    "array": 8,
    "symbol": 9,
    "arraybuffer": 10,
    "typedarray": 11,
    "dataview": 12
}
js_promise_states = {
    "pending": 0,
    "resolved": 1,
    "rejected": 2
}
__callback_refs = []


def descriptive_message(code: str, method: str) -> str:
    return f"While evaluation of {method} method, " + \
           f"ChakraCore returned errornous {hex(code)} code!"


js_globalThis: JSValueRef = JSValueRef()
initial_val = js_globalThis.value
js_undefined: JSValueRef = JSValueRef()
js_null: JSValueRef = JSValueRef()
js_true: JSValueRef = JSValueRef()
js_false: JSValueRef = JSValueRef()
js_array: JSValueRef = JSValueRef()
js_atomics: JSValueRef = JSValueRef()
js_bigint: JSValueRef = JSValueRef()
js_eval_function: JSValueRef = JSValueRef()
js_error: JSValueRef = JSValueRef()
js_error_prototype: JSValueRef = JSValueRef()
js_then: JSValueRef = JSValueRef()
js_reflect: JSValueRef = JSValueRef()


def init_utilitites():
    chakra_core.JsGetGlobalObject(byref(js_globalThis))
    chakra_core.JsGetUndefinedValue(byref(js_undefined))
    chakra_core.JsGetNullValue(byref(js_null))
    chakra_core.JsGetTrueValue(byref(js_true))
    chakra_core.JsGetFalseValue(byref(js_false))


def init_other_utilities():
    pointer(js_error_prototype)[0] = get_prototype(create_error(""))
    pointer(js_error)[0] = get_property(js_error_prototype, "constructor")
    pointer(js_array)[0] = get_property(js_globalThis, "Array")
    pointer(js_atomics)[0] = get_property(js_globalThis, "Atomics")
    pointer(js_bigint)[0] = get_property(js_globalThis, "BigInt")
    pointer(js_eval_function)[0] = get_property(js_globalThis, "eval")
    lazy_function_queue.exec()
    lazy_object_queue.exec()


def str_to_js_string(string: str) -> JSValueRef:
    """
    Converts python string to js string value ref
    """
    string = str(string)  # Making sure
    string_pointer = JSValueRef()
    chakra_core.JsCreateString(create_string_buffer(string.encode("utf8")),
                               len(string), byref(string_pointer))
    return string_pointer


def str_to_array(string: Union[str, int], *, encoding="utf8") -> Array[c_char]:
    string = str(string).encode(encoding)
    return create_string_buffer(string)


def create_runtime(flags: int = 0x22):
    runtime = c_void_p()
    c = chakra_core.JsCreateRuntime(flags, 0, byref(runtime))
    assert c == 0, descriptive_message(c, "create_runtime")
    return runtime


def create_array(length: int = 0):
    a = JSValueRef()
    c = chakra_core.JsCreateArray(length, byref(a))
    assert c == 0, descriptive_message(c, "create_array")
    return a


def to_array(arr: List[JSValueRef]):
    array = create_array(len(arr))
    for index, item in enumerate(arr):
        set_property(array, index, item)
    print(js_value_to_string(array))
    return array


def create_object(props: Optional[PropertyDict] = None) -> JSValueRef:
    obj = JSValueRef()
    c = chakra_core.JsCreateObject(byref(obj))
    assert c == 0, descriptive_message(c, "create_object")
    if props is not None:
        for prop, item in props.items():
            set_property(obj, prop, item)
    return obj


def get_property_id_from_str(string: str) -> JSValueRef:
    prop_id = JSValueRef()
    c = chakra_core.JsCreatePropertyId(str_to_array(string),
                                       len(string), byref(prop_id))
    assert c == 0, descriptive_message(c, "get_property_id_from_str")
    return prop_id


def set_property(obj: JSValueRef,
                 key: Union[str, int],
                 value: JSValueRef, *,
                 strict_mode: StrictModeType = c_true) -> JSValueRef:
    if type(key) is str:
        prop_id = get_property_id_from_str(key)
        c = chakra_core.JsSetProperty(obj, prop_id, value, strict_mode)
    else:
        key = to_number(key)
        c = chakra_core.JsSetIndexedProperty(obj, key, value)
    assert c == 0, descriptive_message(c, "set_property")
    return obj


def set_prototype(obj: JSValueRef, proto: JSValueRef) -> JSValueRef:
    c = chakra_core.JsSetPrototype(obj, proto)
    assert c == 0, descriptive_message(c, "set_prototype")
    return obj


def create_function(callback: c_func_type,
                    name: Optional[str] = None) -> JSValueRef:
    function = JSValueRef()
    p = byref(function)
    if name is None:
        c = chakra_core.JsCreateFunction(callback, 0, p)
    else:
        name_ = str_to_js_string(name)
        c = chakra_core.JsCreateNamedFunction(name_, callback, 0, p)
    assert c == 0, descriptive_message(c, "create_function")
    return function


def create_error(message: str) -> JSValueRef:
    error = JSValueRef()
    c = chakra_core.JsCreateError(str_to_js_string(message), byref(error))
    assert c == 0, descriptive_message(c, "create_error")
    return error


def create_type_error(message: str) -> JSValueRef:
    error = JSValueRef()
    c = chakra_core.JsCreateTypeError(str_to_js_string(message), byref(error))
    assert c == 0, descriptive_message(c, "create_type_error")
    return error


def call(f: JSValueRef, *args, this: JSValueRef = js_undefined) -> JSValueRef:
    _l = len(args) + 1
    a = (JSValueRef * _l)(walk_asparam_chain(this),
                          *map(walk_asparam_chain, args))
    result = JSValueRef()
    c = chakra_core.JsCallFunction(f, a, _l, byref(result))
    assert c == 0, descriptive_message(c, "call")
    return result


def construct(f: JSValueRef, *args,
              this: JSValueRef = js_undefined) -> JSValueRef:
    _l = len(args) + 1
    a = (JSValueRef * _l)(walk_asparam_chain(this),
                          *map(walk_asparam_chain, args))
    result = JSValueRef()
    c = chakra_core.JsConstructObject(f, a, _l, byref(result))
    assert c == 0, descriptive_message(c, "construct")
    return result


def get_own_property_names(value: JSValueRef) -> JSValueRef:
    names = JSValueRef()
    c = chakra_core.JsGetOwnPropertyNames(value, byref(names))
    assert c == 0, descriptive_message(c, "get_own_property_names")
    return names


def clone(value: JSValueRef) -> JSValueRef:
    result = JSValueRef()
    c = chakra_core.JsCloneObject(value, byref(result))
    assert c == 0, descriptive_message(c, "clone")
    return result


def get_prototype(value: JSValueRef) -> JSValueRef:
    proto = JSValueRef()
    c = chakra_core.JsGetPrototype(value, byref(proto))
    assert c == 0, descriptive_message(c, "get_prototype")
    return proto


def get_property(object: JSValueRef, prop: Union[str, int]) -> JSValueRef:
    r = JSValueRef()
    if type(prop) is int:
        c = chakra_core.JsGetIndexedProperty(object, to_number(prop),
                                             byref(r))
    else:
        c = chakra_core.JsGetProperty(object, get_property_id_from_str(prop),
                                      byref(r))
    assert c == 0, descriptive_message(c, "get_property")
    return r


def array_to_iterable(array: JSValueRef) -> Iterable[JSValueRef]:
    length = to_int(get_property(array, "length"))
    return (get_property(array, index) for index in range(0, length))
    # for index in range(0, length):
    #     yield get_property(array, index)


def array_to_list(array: JSValueRef) -> List[JSValueRef]:
    return list(array_to_iterable(array))


def js_eval(code: str) -> JSValueRef:
    return call(Fridge["eval"](), str_to_js_string(code))


def to_object(value: JSValueRef) -> JSValueRef:
    object = JSValueRef()
    c = chakra_core.JsConvertValueToObject(value, byref(object))
    assert c == 0, descriptive_message(c, "to_object")
    return object


def to_number(value: _NumberLike) -> JSValueRef:
    number = JSValueRef()
    if type(value) is POINTER(JSValueRef) or type(value) is JSValueRef:
        c = chakra_core.JsConvertValueToNumber(value, byref(number))
    else:
        c = chakra_core.JsDoubleToNumber(c_longdouble(value), byref(number))
    assert c == 0, descriptive_message(c, "to_number")
    return number


def to_double(value: _NumberLike) -> float:
    number = c_longdouble()
    c = chakra_core.JsNumberToDouble(to_number(value), byref(number))
    assert c == 0, descriptive_message(c, "to_double")
    return number.value


def to_int(value: JSValueRef) -> int:
    value = to_number(value)
    number = c_int(0)
    c = chakra_core.JsNumberToInt(value, byref(number))
    assert c == 0, descriptive_message(c, "to_int")
    return number.value


def prepare_return_value(value: JSValueRef) -> int:
    return value.value


def typeof(value: JSValueRef) -> int:
    T = c_int(0)
    c = chakra_core.JsGetValueType(value, byref(T))
    assert c == 0, descriptive_message(c, "typeof")
    return T.value


def throw(error: JSValueRef) -> None:
    c = chakra_core.JsSetException(error)
    assert c == 0, descriptive_message(c, "throw")


def create_promise() -> Tuple[JSValueRef, JSValueRef, JSValueRef]:
    promise = JSValueRef()
    resolve = JSValueRef()
    reject = JSValueRef()
    c = chakra_core.JsCreatePromise(byref(promise),
                                    byref(resolve),
                                    byref(reject))
    assert c == 0, descriptive_message(c, "create_promise")
    return promise, resolve, reject


def get_promise_result(value: JSValueRef) -> JSValueRef:
    r = JSValueRef()
    c = chakra_core.JsGetPromiseResult(value, byref(r))
    assert c == 0, descriptive_message(c, "get_promise_result")
    return r


def get_promise_state(value: JSValueRef) -> int:
    state = c_int()
    c = chakra_core.JsGetPromiseState(value, byref(state))
    assert c == 0, descriptive_message(c, "get_promise_state")
    return state.value


def inspect(value: JSValueRef, indent="\t") -> str:
    props = array_to_iterable(get_own_property_names(value))
    for prop in props:
        pass
    re.compile()
    return js_value_to_string(value)


def set_promise_callback(callback):
    __callback_refs.append(callback)
    c = chakra_core.JsSetPromiseContinuationCallback(callback, 0)
    assert c == 0, descriptive_message(c, "set_promise_callback")


def set_rejections_callback(callback):
    __callback_refs.append(callback)
    c = chakra_core.JsSetHostPromiseRejectionTracker(callback, 0)
    assert c == 0, descriptive_message(c, "set_rejections_callback")


def set_current_context(context):
    c = chakra_core.JsSetCurrentContext(context, 0)
    assert c == 0, descriptive_message(c, "set_current_context")


def set_exception(record, ex):
    print(ex)
    c = chakra_core.JsSetModuleHostInfo(record, 1, ex)
    assert c == 0, descriptive_message(c, "set_exception")


def set_fetch_importing_module_callback(callback):
    _n = "set_fetch_importing_module_callback"
    callback = cast(callback, c_void_p)
    __callback_refs.append(callback)
    c = chakra_core.JsSetModuleHostInfo(None, 4, callback)
    assert c == 0, descriptive_message(c, _n)


def set_fetch_importing_module_from_script_callback(callback):
    _n = "set_fetch_importing_module_from_script_callback"
    callback = cast(callback, c_void_p)
    __callback_refs.append(callback)
    c = chakra_core.JsSetModuleHostInfo(None, 5, callback)
    assert c == 0, descriptive_message(c, _n)


def set_url(record, url):
    url = cast(url, c_void_p)
    __callback_refs.append(url)  # not callback, but why not to keep it?
    c = chakra_core.JsSetModuleHostInfo(record, 6, url)
    assert c == 0, descriptive_message(c, "set_url")


def set_import_meta_callback(callback):
    __callback_refs.append(callback)
    c = chakra_core.JsSetModuleHostInfo(None, 7, callback)
    assert c == 0, descriptive_message(c, "set_import_meta_callback")


def set_module_ready_callback(callback):
    @CFUNCTYPE(c_int, c_void_p, c_void_p)
    def dummy(module, ex):
        callback(module, ex)
        return 0
    __callback_refs.append(dummy)
    c = chakra_core.JsSetModuleHostInfo(None, 8, dummy)
    assert c == 0, descriptive_message(c, "set_module_ready_callback")


def set_module_notify_callback(callback):
    @CFUNCTYPE(c_int, c_void_p, c_void_p)
    def dummy(module, ex):
        # print("calling dummy6")
        callback(module, ex)
        return 0
    __callback_refs.append(dummy)
    c = chakra_core.JsSetModuleHostInfo(None, 3, dummy)
    assert c == 0, descriptive_message(c, "set_module_notify_callback")


def is_callable(value: JSValueRef) -> bool:
    result = c_bool()
    c = chakra_core.JsIsCallable(value, byref(result))
    if c == 0x1000c:
        return False
    assert c == 0, descriptive_message(c, "is_callable")
    return bool(result)


def is_constructor(value: JSValueRef) -> bool:
    result = c_bool()
    c = chakra_core.JsIsConstructor(value, byref(result))
    if c == 0x1000c:
        return False
    assert c == 0, descriptive_message(c, "is_constructor")
    return bool(result)


def parse_module_source(record: JSModuleRecord,
                        context_count: int,
                        script: c_char_p,
                        flags: int = 0) -> JSValueRef:
    ex = JSValueRef()
    c = chakra_core.JsParseModuleSource(record,
                                        context_count,
                                        script,
                                        len(script),
                                        flags,
                                        byref(ex))
    assert c == 0, descriptive_message(c, "parse_module_source")
    return ex


def init_module_record(ref_module: JSModuleRecord,
                       url: POINTER(c_byte)) -> JSModuleRecord:
    record = JSValueRef()
    c = chakra_core.JsInitializeModuleRecord(ref_module,
                                             url,
                                             byref(record))
    assert c == 0, descriptive_message(c, "parse_module_source")
    return record


def create_external_array_buffer(script) -> JSRef:
    script_source = JSRef()
    c = chakra_core.JsCreateExternalArrayBuffer(script, len(script), 0,
                                                0, byref(script_source))
    assert c == 0, descriptive_message(c, "create_external_array_buffer")
    return script_source


def dispose_runtime(runtime) -> None:
    c = chakra_core.JsDisposeRuntime(runtime)
    assert c == 0, descriptive_message(c, "dispose_runtime")


def create_context(runtime: c_void_p):
    context = JSValueRef()
    c = chakra_core.JsCreateContext(runtime, byref(context))
    assert c == 0, descriptive_message(c, "create_context")
    return context


def get_exception():
    ex = c_void_p()
    c = chakra_core.JsGetAndClearException(byref(ex))
    if c == 0x10001:
        print("no-error")
        return None
    assert c == 0, descriptive_message(c, "get_exception")
    return ex


def get_runtime_memory_limit(runtime: c_void_p) -> int:
    memory_limit = c_size_t()
    c = chakra_core.JsGetRuntimeMemoryLimit(runtime, byref(memory_limit))
    assert c == 0, descriptive_message(c, "get_runtime_memory_limit")
    return memory_limit.value


def set_runtime_memory_limit(runtime: c_void_p, memory_limit: int) -> int:
    c = chakra_core.JsSetRuntimeMemoryLimit(runtime, c_size_t(memory_limit))
    assert c == 0, descriptive_message(c, "set_runtime_memory_limit")
    return memory_limit.value


def get_runtime_memory_usage(runtime: c_void_p) -> int:
    memory_limit = c_size_t()
    c = chakra_core.JsGetRuntimeMemoryUsage(runtime, byref(memory_limit))
    assert c == 0, descriptive_message(c, "get_runtime_memory_usage")
    return memory_limit.value


def run_module(module: c_void_p) -> JSValueRef:
    result = JSValueRef()
    c = chakra_core.JsModuleEvaluation(module, byref(result))
    assert c == 0, descriptive_message(c, "run_module")
    return result


def run_script(script: Any, filename: c_char_p) -> JSValueRef:
    result = JSValueRef()
    c = chakra_core.JsRun(script, 0, filename,
                          0x22, byref(result))
    assert c == 0, descriptive_message(c, "run_script")
    return result


def create_c_string(string: str):
    result = JSValueRef()
    c = chakra_core.JsCreateString(string, len(string), byref(result))
    assert c == 0, descriptive_message(c, "create_c_string")
    return result


def c_array_to_iterator(array, length, offset=0) -> \
        Generator[Any, None, JSValueRef]:
    for index in range(offset, length):
        yield array[index]


def add_ref(ref: JSValueRef):
    chakra_core.JsAddRef(ref, 0)


def js_release(ref: JSValueRef):
    chakra_core.JsRelease(ref, 0)


def js_value_to_string(value: JSValueRef) -> str:
    """
    Converts JavaScript value to python string
    """
    # Convert script result to String in JavaScript;
    # redundant if script returns a String
    result_js_string = JSValueRef()
    chakra_core.JsConvertValueToString(value, byref(result_js_string))

    string_length = c_size_t()
    # Get buffer size needed for the result string
    chakra_core.JsCopyString(result_js_string, 0, 0, byref(string_length))

    # buffer is big enough to store the result
    result_string = create_string_buffer(string_length.value + 1)

    # Get String from JSValueRef
    chakra_core.JsCopyString(result_js_string, byref(result_string),
                             string_length.value + 1, 0)

    # Set `null-ending` to the end
    result_string_last_byte = (c_char * string_length.value) \
        .from_address(addressof(result_string))
    result_string_last_byte = '\0'  # noqa: F841
    return str(result_string.value, "utf8")
