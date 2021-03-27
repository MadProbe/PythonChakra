from os import getcwd, path
import os
from typing import *

import requests
from whatwg_url import Url as URL
from whatwg_url import is_valid_url, parse_url

from cookies import cookies
from dll_wrapper import *
from fifo_queue import FIFOQueue


PathResolverFunctionType = Callable[[Callable[[None, str, str], URL], str, str], URL]
LoaderFunctionType = Callable[[Callable[[None, str], URL], str], URL]


class WTFException(Exception):
    """
    Exception is raised when highly unexcepted thing occurs
    """
    pass


class JavaScriptModule:
    __slots__ = "_as_parameter_", "spec", "code", "cookie", "directory", "fullpath", "module", "parent", "root"

    def __init__(self, specifier: URL, code: str, importer: c_void_p, root: bool = False, /) -> None:
        self.root = root
        self.cookie = cookies.increment()
        if importer is not None:
            self.parent = importer
        else:
            self.parent = None
        self.directory = path.dirname(("%s://%s/%s" % (specifier.scheme, specifier.hostname, specifier.path)))
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
        script = create_string_buffer(self.code.encode("UTF-16"))
        # TODO: Properly handle module code parse exceptions
        set_exception(self, parse_module_source(self,
                                                self.cookie,
                                                script,
                                                len(script),
                                                0))

    def eval(self):
        run_module(self)

    def dispose(self):
        js_release(self.spec)
        js_release(self)
        self.spec = None


def default_path_resolver(_, base, spec) -> URL:
    if is_valid_url(spec):
        return parse_url(spec)
    elif spec.startswith("/") or spec.startswith("./") or spec.startswith("../"):
        return parse_url(spec, base=base)
    raise SyntaxError("Cannot resolve path %s" % spec)


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
        if os.name == "posix":
            href = "/" + href
        with open(href, 'r') as file:
            return ''.join(file.readlines())
    else:
        raise TypeError(f"Path scheme \"{scheme}\" is not supported")


def default_import_meta_callback(module: Union[JavaScriptModule, None], object: JSValueRef):
    if module is not None and object.value != 0 and object.value is not None:
        set_property(object, "url", module.spec)


class ModuleFIFOQueue(FIFOQueue):
    def run(_, module: JavaScriptModule):
        module.parse()


class ModuleRuntime:
    __slots__ = "modules", "path_resolver", "loader", "runtime", "queue"

    def __init__(self, runtime, path_resolver: PathResolverFunctionType = None, loader: LoaderFunctionType = None) -> None:
        self.modules = dict()
        self.path_resolver = path_resolver or default_path_resolver
        self.loader = loader or default_loader
        self.runtime = runtime
        self.queue = ModuleFIFOQueue()

    def add_module(self, spec: str, module: JavaScriptModule) -> None:
        self.modules[spec] = module

    def get_module(self, specifier: str, /) -> Union[JavaScriptModule, None]:
        return self.modules[specifier]

    def get_module_by_pointer(self, pointer: c_void_p) -> Union[JavaScriptModule, None]:
        if pointer is None:
            return None
        module: JavaScriptModule
        for module in self.modules:
            if module._as_parameter_.value == pointer.value:
                return

    def on_module_fetch(self, importer: Union[c_void_p, None], specifier: JSValueRef, module_record_p: POINTER(c_void_p), /):
        print(type(module_record_p))
        spec = js_value_to_string(specifier)
        parent_module = self.get_module_by_pointer(importer)
        pathbase = parse_url("file:///" + getcwd())
        if importer is not None:
            if parent_module is None:
                raise WTFException("WTF???")
            pathbase = parent_module.directory
        spec: URL = self.path_resolver(default_path_resolver, pathbase, spec)
        if type(spec) is not URL:
            raise TypeError
        module = self.get_module(spec)
        if module is not None:
            module_record_p[0] = module
            return
        code = str(self.loader(default_loader, spec))
        module = JavaScriptModule(spec, code, parent_module, False)
        self.queue.append(module)
        module_record_p[0] = module

    def on_module_ready(self, module: Union[JavaScriptModule, None], exception: Union[JSValueRef, None], /):
        if module.root and exception is None:
            module.eval()
        elif module is not None and exception is not None:
            print(js_value_to_string(exception))
        

    def attach_callcacks(self):
        @WINFUNCTYPE(c_void_p, JSRef, JSValueRef, POINTER(c_void_p))
        def dummy1(ref_module, specifier, module_record):
            self.on_module_fetch(ref_module, specifier, module_record)
            return 0

        @WINFUNCTYPE(c_void_p, c_void_p, JSValueRef, POINTER(c_void_p))
        def dummy2(_, specifier, module_record):  # just ignore the source context variable
            self.on_module_fetch(None, specifier, module_record)
            return 0


        def dummy3(ref_module, ex):
            module = self.get_module_by_pointer(ref_module)
            module is not None and self.on_module_ready(module, ex)

        def dummy4(ref_module, ex):
            pass
        set_fetch_importing_module_callback(dummy1)
        set_fetch_importing_module_from_script_callback(dummy2)
        set_import_meta_callback(default_import_meta_callback)
        set_module_ready_callback(dummy4)
        set_module_notify_callback(dummy3)
