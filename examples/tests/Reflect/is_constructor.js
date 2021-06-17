import { assert, assertNot, assertType, Tests } from "../__impl__.js"

const name = "Reflect.isConstructor";
Tests.run(name, {
    [`${ name }'s Existance`]() {
        assertType(Reflect.isConstructor, "function");
    },
    [`${ name } called on constructors`]() {
        assert(Reflect.isConstructor(function () { }));
        assert(Reflect.isConstructor(class { }), "class {}");
    },
    [`${ name } called on non-constructors`]() {
        assertNot(Reflect.isConstructor(() => { console.log("1") }));
        assertNot(Reflect.isConstructor(async () => { }));
        assertNot(Reflect.isConstructor(function* () { }), "function* () { }");
        assertNot(Reflect.isConstructor(async function () { }), "async function () { }");
        assertNot(Reflect.isConstructor(async function* () { }), "async function* () { }");
        assertNot(Reflect.isConstructor(0));
        assertNot(Reflect.isConstructor({}));
        assertNot(Reflect.isConstructor(true));
        assertNot(Reflect.isConstructor(false));
        assertNot(Reflect.isConstructor(/* void 0 */));
    }
});
