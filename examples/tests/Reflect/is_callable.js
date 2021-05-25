import { assert, Tests } from "../__impl__.js"

const name = "Reflect.isCallable";
Tests.run(name, {
    [`${ name }'s Existance`]() {
        assert(typeof Reflect.isCallable === "function");
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
        assert(!Reflect.isCallable(class { }), "class {}"); // Fails for now.
        assert(!Reflect.isCallable(0));
        assert(!Reflect.isCallable({}));
        assert(!Reflect.isCallable(true));
        assert(!Reflect.isCallable(false));
        assert(!Reflect.isCallable());
    }
});
