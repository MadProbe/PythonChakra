from os import getcwd
import os
from promise_queue import PromiseFIFOQueue
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
    __slots__ = "_as_parameter_", "spec", "code", "cookie", "directory", "fullpath", "module", "parent", "root", "__promise_queue"

    def __init__(self, queue: PromiseFIFOQueue, specifier: URL, code: str, importer: c_void_p, root: bool = False, /) -> None:
        self.root = root
        self.__promise_queue = queue
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
        print(module)
        add_ref(module)
        self.module = module
        self._as_parameter_ = module
        self.code = code
        set_url(module, self.spec)

    def parse(self):
        script = create_string_buffer((self.code + "\0").encode('UTF-16'))
        # TODO: Properly handle syntax errors of the module code
        parse_module_source(self,
                            self.cookie,
                            script,
                            len(script),
                            0)
        print(self.root, "parse_module_source")

    def eval(self):
        run_module(self.module)
        # self.__promise_queue.exec()

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
    __slots__ = "__promise_queue", "modules", "path_resolver", "loader", "runtime", "queue"

    def __init__(self, runtime, __promise_queue: PromiseFIFOQueue,
                 path_resolver: PathResolverFunctionType = None,
                 loader: LoaderFunctionType = None) -> None:
        self.modules = dict()
        self.path_resolver = path_resolver or default_path_resolver
        self.loader = loader or default_loader
        self.runtime = runtime
        self.queue = ModuleFIFOQueue()
        self.__promise_queue = __promise_queue

    def add_module(self, spec: str, module: JavaScriptModule) -> None:
        self.modules[spec] = module

    def get_module(self, specifier: str, /) -> Union[JavaScriptModule, None]:
        return self.modules.get(specifier)

    def get_module_by_pointer(self, pointer: c_void_p) -> Union[JavaScriptModule, None]:
        if pointer is None:
            return None
        module: JavaScriptModule
        if type(pointer) is int:
            for module in self.modules.values():
                print("asdjfsdf-iteree-1:", module._as_parameter_.value, pointer)
                if module._as_parameter_.value == pointer:
                    return module
        else:
            for module in self.modules.values():
                print("asdjfsdf-iteree-2:", module._as_parameter_.value, pointer)
                if module._as_parameter_.value == pointer.value:
                    return module

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
            module_record_p[0] = module.module.value
            return
        code = str(self.loader(default_loader, spec))
        module = JavaScriptModule(self.__promise_queue, spec, code, parent_module, importer is None)
        self.queue.append(module)
        module_record_p[0] = module.module.value

    def on_module_ready(self, module: Union[JavaScriptModule, None], exception: Union[JSValueRef, None], /):
        if module.root and exception is None:
            module.eval()
        elif module is not None and exception is not None:
            print(js_value_to_string(c_void_p(exception)))
        

    def attach_callcacks(self):
        @CFUNCTYPE(c_int, JSRef, JSValueRef, POINTER(c_void_p))
        def dummy1(ref_module, specifier, module_record):
            self.on_module_fetch(c_void_p(ref_module), c_void_p(specifier), module_record)
            return 0

        @CFUNCTYPE(c_int, c_void_p, JSValueRef, POINTER(c_void_p))
        def dummy2(_, specifier, module_record):  # just ignore the source context variable
            self.on_module_fetch(None, c_void_p(specifier), module_record)
            return 0


        def dummy3(ref_module, ex):
            print("dummy3")
            module = self.get_module_by_pointer(ref_module)
            module is not None and self.on_module_ready(module, ex)
            return 0

        def dummy4(ref_module, ex):
            pass

        @CFUNCTYPE(c_int, c_void_p, c_void_p)
        def import_meta_callback_wrapped(module, object):
            module = self.get_module_by_pointer(c_void_p(module))
            default_import_meta_callback(module, c_void_p(object))
            return 0
        set_fetch_importing_module_callback(dummy1)
        set_fetch_importing_module_from_script_callback(dummy2)
        set_import_meta_callback(import_meta_callback_wrapped)
        set_module_notify_callback(dummy3)
        set_module_ready_callback(dummy4)
