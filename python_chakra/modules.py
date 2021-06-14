from __future__ import annotations

from os import getcwd, name
from typing import *

import requests
from whatwg_url import Url as URL, is_valid_url, parse_url

from .dll_wrapper import *
from .utils import FIFOQueue, cookies


class JSModule:
    __slots__ = "_as_parameter_", "spec", "code", "cookie", "directory", \
                "fullpath", "module", "parent", "root"
    root: bool
    spec: JSValueRef
    code: str
    cookie: int
    directory: URL
    fullpath: str
    module: JSModuleRecord
    parent: Optional[JSModuleRecord]
    _as_parameter_: JSModuleRecord

    def __init__(self, specifier: URL, code: str, importer: c_void_p,
                 root: bool = False) -> None:
        self.root = root
        self.cookie = cookies.increment()
        if importer is not None:
            self.parent = importer
        else:
            self.parent = None
        self.directory = parse_url(".", base=str(specifier))
        self.fullpath = specifier.href
        self.spec = str_to_js_string(str(specifier))
        add_ref(self.spec)
        module = init_module_record(importer, self.spec)
        add_ref(module)
        self.module = module
        self._as_parameter_ = module
        self.code = code
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


def default_path_resolver(_, base: str, spec: str) -> URL:
    if is_valid_url(spec):
        return parse_url(spec)
    elif spec.startswith(("/", "./", "../")):
        return parse_url(spec, base=base)
    raise SyntaxError(f"Cannot resolve path {spec}")


def default_loader(_, url: URL):
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


def default_import_meta_callback(module: ModuleOrNone,
                                 object: JSValueRef):
    if module is not None and object.value != 0 and object.value is not None:
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
                 path_resolver: Optional[PathResolverFunctionType] = None,
                 loader: Optional[LoaderFunctionType] = None) -> None:
        self.modules = dict()
        self.path_resolver = path_resolver or default_path_resolver
        self.loader = loader or default_loader
        self.runtime = runtime
        module_queue.clear()

    def add_module(self, spec: str, module: JSModule) -> None:
        self.modules[spec] = module

    def get_module(self, specifier: str) -> Optional[JSModule]:
        return self.modules.get(specifier)

    def get_module_by_pointer(self, pointer: JSRef) -> Optional[JSModule]:
        if pointer is None:
            return None
        if type(pointer) is int:
            for module in self.modules.values():
                if module._as_parameter_.value == pointer:
                    return module
        else:
            for module in self.modules.values():
                if module._as_parameter_.value == pointer.value:
                    return module

    def on_module_fetch(self, importer: Optional[JSRef],
                        specifier: JSValueRef,
                        module_record_p: POINTER(JSRef)):
        spec = js_value_to_string(specifier)
        parent_module = self.get_module_by_pointer(importer)
        pathbase = parse_url("file:///" + getcwd())
        if importer is not None:
            if parent_module is None:
                raise Exception(f"Couldn't resolve module {importer}")
            pathbase = parent_module.directory
        spec: URL = self.path_resolver(default_path_resolver, pathbase, spec)
        if type(spec) is not URL:
            raise TypeError
        module = self.get_module(spec)
        if module is None:
            code = str(self.loader(default_loader, spec))
            module = JSModule(spec, code, parent_module, importer is None)
            self.add_module(str(spec), module)
            module_queue.append(module)
        module_record_p[0] = module.module.value

    def on_module_ready(self, module: Optional[JSModule],
                        exception: Optional[JSValueRef]):
        if module is not None:
            if exception is None:
                module.eval()
            elif exception:
                print(js_value_to_string(c_void_p(exception)))

    def attach_callcacks(self):
        @CFUNCTYPE(c_int, JSRef, JSValueRef, POINTER(c_void_p))
        def dummy1(ref_module, specifier, module_record):
            self.on_module_fetch(c_void_p(ref_module),
                                 c_void_p(specifier),
                                 module_record)
            return 0

        @CFUNCTYPE(c_int, c_void_p, JSValueRef, POINTER(JSRef))
        def dummy2(_, specifier, module_record):
            # just ignore the source context variable
            self.on_module_fetch(None, c_void_p(specifier), module_record)
            return 0

        def dummy3(ref_module, ex):
            # print("dummy3")
            module = self.get_module_by_pointer(ref_module)
            module is not None and self.on_module_ready(module, ex)
            return 0

        def dummy4(ref_module, ex):
            pass

        @CFUNCTYPE(c_int, JSRef, JSValueRef)
        def import_meta_callback_wrapped(module, object):
            module = self.get_module_by_pointer(c_void_p(module))
            default_import_meta_callback(module, c_void_p(object))
            return 0
        set_fetch_importing_module_callback(dummy1)
        set_fetch_importing_module_from_script_callback(dummy2)
        set_import_meta_callback(import_meta_callback_wrapped)
        set_module_notify_callback(dummy3)
        set_module_ready_callback(dummy4)


_DefaultPathResolverFunction = Callable[[None, str, str], URL]
PathResolverFunctionType = Callable[[_DefaultPathResolverFunction,
                                     str, str], URL]
_DefaultLoaderFunctionType = Callable[[None, str], URL]
LoaderFunctionType = Callable[[_DefaultLoaderFunctionType, str], URL]
ModuleOrNone = Optional[JSModule]
module_queue = ModuleFIFOQueue()
