from __future__ import annotations

from csv import reader
from ctypes import CFUNCTYPE, POINTER, c_int, c_void_p
from functools import partial
from json.decoder import JSONDecoder
from os import getcwd, name, urandom
from os.path import dirname
from typing import Any, Callable, Dict, Generator, Iterable, List, Optional, \
    TypeVar, Union

import regex as re
import requests
from toml import loads
from whatwg_url import Url as URL, is_valid_url, parse_url
from yaml import safe_load

from .dll_wrapper import JSModuleRecord, JSRef, JSValueRef, add_ref, \
    init_module_record, js_release, js_value_to_string, parse_module_source, \
    promise_queue, run_module, set_fetch_importing_module_callback, \
    set_fetch_importing_module_from_script_callback, \
    set_import_meta_callback, set_module_notify_callback, \
    set_module_ready_callback, set_property, set_url, str_to_array, \
    str_to_js_string
from .utils import FIFOQueue, cookies


def flatten(i: Iterable[Iterable[_T]]) -> Generator[_T, None, None]:
    for iterator in i:
        yield from iterator


with open(f"{dirname(__file__)}/js-keywords-list.csv") as f:
    _KEYWORDS = list(flatten(reader(f.readlines())))


def _skip_args(f, n):
    return lambda *args: f(*args[n:])


def _gen_random_name():
    return f"__$$${urandom(8).hex()}$$$__"


class JSModule:
    __slots__ = "_as_parameter_", "spec", "code", "cookie", "directory", \
                "fullpath", "parent", "root"
    root: bool
    spec: JSValueRef
    code: str
    cookie: int
    directory: URL
    fullpath: str
    parent: Optional[JSModuleRecord]
    _as_parameter_: JSModuleRecord

    def __init__(self, specifier: URL, code: str,
                 importer: Optional[JSModuleRecord] = None) -> None:
        self.cookie = cookies.increment()
        self.directory = parse_url(".", base=str(specifier))
        self.fullpath = specifier.href
        self.root = importer is None
        self.spec = str_to_js_string(str(specifier))
        self.parent = importer
        add_ref(self.spec)
        module = init_module_record(importer, self.spec)
        add_ref(module)
        self._as_parameter_ = module
        self.code = dafault_transformer(code, specifier)
        set_url(module, self.spec)

    def parse(self):
        script = str_to_array(self.code, encoding="UTF-16")
        parse_module_source(self, self.cookie, script)
        if self.root:
            module_queue.exec()

    def eval(self):
        run_module(self)
        promise_queue.exec()

    def dispose(self):
        js_release(self.spec)
        js_release(self)
        self.spec = None
        self._as_parameter_ = None


def default_path_resolver(base: str, spec: str) -> URL:
    if is_valid_url(spec):
        return parse_url(spec)
    elif spec.startswith(("/", "./", "../")):
        return parse_url(spec, base=base)
    raise SyntaxError(f"Cannot resolve path {spec}")


def default_loader(url: URL):
    scheme = url.scheme
    if scheme == "https" or scheme == "http":
        response = requests.get(url.href)
        response.raise_for_status()
        return response.text
    elif scheme == "file":
        href = url.href[5:]
        while href[0] == "/":
            href = href[1:]
        if name == "posix":
            href = "/" + href
        with open(href, 'r') as file:
            return file.read()
    else:
        raise TypeError(f"Path scheme \"{scheme}\" is not supported")


class _ModuleEmitter:
    @classmethod
    def emit(cls, structure: _Emittable) -> str:
        emitted = cls._emit(structure)
        if type(structure) is dict:
            structure: Dict[str, _Emittable]
            regex = re.compile(r"^[_\$\p{ID_START}]\p{ID_CONTINUE}*$", re.M)
            keys = [k for k in structure.keys()
                    if re.search(regex, k) and k not in _KEYWORDS]
            name = _gen_random_name()
            while name in keys:
                # avoid situiations where random name
                # is a property name of parsed file
                name = _gen_random_name()
            code = f"const {name} = {emitted};\n"
            for k in keys:
                code += f"export const {k} = {name}.{k};\n"
            code += f"export default {name};\n"
            return code
        else:
            return f"export default {emitted};\n"

    @classmethod
    def _emit(cls, value: _Emittable) -> str:
        if type(value) is dict:
            return cls._emit_dict(value)
        if type(value) is list:
            return cls._emit_list(value)
        return cls._emit_simple(value)

    @classmethod
    def _emit_dict(cls, value: Dict[str, _Emittable]) -> str:
        f = cls._emit
        return f'{{{",".join(f(k) + ":" + f(v) for k, v in value.items())}}}'

    @classmethod
    def _emit_list(cls, value: List[_Emittable]) -> str:
        return f"[{','.join(map(cls._emit, value))}]"

    @staticmethod
    def _emit_simple(value: _EmittableSimple) -> str:
        if type(value) is str:
            return "\"" + value \
                .replace("\\", "\\\\") \
                .replace("\n", "\\n") \
                .replace("\r", "\\r") \
                .replace("\"", "\\\"") + "\""
        if type(value) is int:
            return str(value)
        if type(value) is float:
            if value == float("nan"):
                return "NaN"
            if value == float("inf"):
                return "Infinity"
            if value == float("-inf"):
                return "-Infinity"
            return str(value)
        if value is None:
            return "null"
        if value is True:
            return "true"
        if value is False:
            return "false"
        raise TypeError


def dafault_transformer(code: str, url: URL):
    regex = re.compile(r"""^(?:/[^/]+)+(\.[^\.]+)+$""", re.M | re.U)
    extension = re.match(regex, url.path).groups()[0]
    if extension in (".yml", ".yaml"):
        return _ModuleEmitter.emit(safe_load(code))
    elif extension == ".json":
        return _ModuleEmitter.emit(decoder.decode(code))
    elif extension == ".toml":
        return _ModuleEmitter.emit(loads(code))
    elif extension == ".csv":
        return _ModuleEmitter.emit(list(flatten(reader(code.splitlines()))))
    else:
        return code


def default_import_meta_callback(module: JSModule, object: JSValueRef):
    set_property(object, "url", module.spec)


class ModuleFIFOQueue(FIFOQueue[JSModule]):
    def run(_, module: JSModule):
        module.parse()


class ModuleRuntime:
    # TODO: Properly handle errors
    __slots__ = "modules", "path_resolver", "loader", "runtime", "queue"
    modules: Dict[str, JSModule]
    path_resolver: PathResolverFunctionType
    loader: LoaderFunctionType

    def __init__(self, runtime: Any,
                 path_resolver: Optional[PathResolverFunctionType] =
                 _skip_args(default_path_resolver, 1),
                 loader: Optional[LoaderFunctionType] =
                 _skip_args(default_loader, 1)) -> None:
        self.modules = dict()
        self.path_resolver = partial(path_resolver, default_path_resolver)
        self.loader = partial(loader, default_loader)
        self.runtime = runtime
        module_queue.clear()

    def add_module(self, spec: str, module: JSModule) -> None:
        self.modules[spec] = module

    def get_module(self, specifier: str) -> Optional[JSModule]:
        return self.modules.get(specifier)

    def get_module_by_pointer(self, ref: JSModuleRecord) -> Optional[JSModule]:
        if ref is None:
            return None
        for module in self.modules.values():
            if module._as_parameter_.value == ref.value:
                return module

    def on_module_fetch(self, importer: Optional[JSModuleRecord],
                        specifier: JSValueRef,
                        module_record_p: POINTER(JSModuleRecord)):
        spec = js_value_to_string(specifier)
        parent_module = self.get_module_by_pointer(importer)
        pathbase = parse_url("file:///" + getcwd())
        if importer is not None:
            if parent_module is None:
                raise Exception(f"Couldn't resolve module {importer}")
            pathbase = parent_module.directory
        spec: URL = self.path_resolver(pathbase, spec)
        if type(spec) is not URL:
            raise TypeError
        module = self.get_module(spec)
        if module is None:
            code = str(self.loader(spec))
            module = JSModule(spec, code, parent_module)
            self.add_module(str(spec), module)
            module_queue.append(module)
        module_record_p[0] = module._as_parameter_.value

    def on_module_ready(self, module: JSModule,
                        exception: Optional[JSValueRef]) -> None:
        if exception is None:
            module.eval()
        else:
            print(js_value_to_string(JSValueRef(exception)))

    def attach_callcacks(self) -> None:
        @CFUNCTYPE(c_int, JSModuleRecord, JSValueRef, POINTER(JSModuleRecord))
        def dummy1(ref_module, specifier, module_record):
            self.on_module_fetch(JSModuleRecord(ref_module),
                                 JSValueRef(specifier),
                                 module_record)
            return 0

        @CFUNCTYPE(c_int, c_void_p, JSValueRef, POINTER(JSRef))
        def dummy2(_, specifier, module_record):
            # just ignore the source context variable
            self.on_module_fetch(None, JSValueRef(specifier), module_record)

        def dummy3(ref_module, ex):
            module = self.get_module_by_pointer(JSModuleRecord(ref_module))
            module and self.on_module_ready(module, ex)

        def dummy4(ref_module, ex):
            pass

        @CFUNCTYPE(c_int, JSModuleRecord, JSValueRef)
        def import_meta_callback_wrapped(module, object):
            module = self.get_module_by_pointer(JSModuleRecord(module))
            if module and object:
                default_import_meta_callback(module, JSValueRef(object))
            else:
                raise RuntimeError("The impossible happened - module or "
                                   "import.meta object are nullptr!")
            return 0
        set_fetch_importing_module_callback(dummy1)
        set_fetch_importing_module_from_script_callback(dummy2)
        set_import_meta_callback(import_meta_callback_wrapped)
        set_module_notify_callback(dummy3)
        set_module_ready_callback(dummy4)


PathResolverFunctionType = Callable[[Callable[[str, str], URL], str, str], URL]
LoaderFunctionType = Callable[[Callable[[str], URL], str], URL]
module_queue = ModuleFIFOQueue()
_EmittableSimple = Union[str, int, float, bool, None]
_Emittable = Union[List['_Emittable'],
                   Dict[str, '_Emittable'],
                   _EmittableSimple]
_T = TypeVar("_T")
decoder = JSONDecoder()
