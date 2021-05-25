import { assert, assertNot, assertType, Tests } from "../__impl__.js"

const name = "Reflect.isCallable";
Tests.run(name, {
    [`${ name }'s Existance`]() {
        assertType(Reflect.isCallable, "function");
    },
    [`${ name } called on functions`]() {
        assert(Reflect.isCallable(() => { console.log("1") }));
        assert(Reflect.isCallable(async () => { }));
        assert(Reflect.isCallable(function () { }));
        assert(Reflect.isCallable(function* () { }), "function* () { }");
        assert(Reflect.isCallable(async function () { }), "async function () { }");
        assert(Reflect.isCallable(async function* () { }), "async function* () { }");
    },
    [`${ name } called on non-functions`]() {
        assertNot(!Reflect.isCallable(class { }), "class {}"); // Fails for now, @see chakra-core/ChakraCore#6720.
        assertNot(!Reflect.isCallable(0));
        assertNot(!Reflect.isCallable({}));
        assertNot(!Reflect.isCallable(true));
        assertNot(!Reflect.isCallable(false));
        assertNot(!Reflect.isCallable(/* void 0 */));
    }
});
