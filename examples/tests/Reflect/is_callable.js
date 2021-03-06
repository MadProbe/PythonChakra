import { assert, assertNot, assertType, Tests } from "../__impl__.js";

const name = "Reflect.isCallable";
Tests.run(name, {
    [`${ name }'s Existance`]() {
        assertType(Reflect.isCallable, "function");
    },
    [`${ name } called on functions`]() {
        assert(Reflect.isCallable(() => { }), "() => { }");
        assert(Reflect.isCallable(async () => { }), "async () => { }");
        assert(Reflect.isCallable(function () { }), "function () { }");
        assert(Reflect.isCallable(function* () { }), "function* () { }");
        assert(Reflect.isCallable(async function () { }), "async function () { }");
        assert(Reflect.isCallable(async function* () { }), "async function* () { }");
    },
    [`${ name } called on non-functions`]() {
        assertNot(Reflect.isCallable(Math), "Math");
        assertNot(Reflect.isCallable(class { }), "class { }");
        assertNot(Reflect.isCallable(0), "0");
        assertNot(Reflect.isCallable({}), "{}");
        assertNot(Reflect.isCallable(true), "true");
        assertNot(Reflect.isCallable(false), "false");
        assertNot(Reflect.isCallable(/* void 0 */), "void 0");
    }
});
