import { assert, assertType } from "../__impl__.js";

assert(__from_wrapper__ === true, "__from_wrapper__ must be defined and must have value `true`");
assertType(console, "object", `console must be typeof object, got: ${ typeof console }`);
