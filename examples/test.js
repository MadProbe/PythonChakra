// console.log("12345")
{
    const s = "-".repeat(15);
    let i = 0;
    globalThis.test = function () {
        const i_ = i++;
        console.log(`${ s } Start - ${ i_ } ${ s }`);
        Promise.resolve().then(() => (console.log(1, Promise.resolve(2).then(() => (console.log(5, Promise.resolve(6).then(console.log), 7), console.log(8))), 3), console.log(4)));
        console.log(`${ s } End - ${ i_ } ${ s }`);
    }
}
import'./test2.js';
await test()
await Promise.resolve(1).then(console.log)
console.log(import.meta.url)

// try {
//     console.log("1 + 1", 1 + 1);
// } catch (error) {
    
// }
// console.log("124");
await test()
await import("./test3.js").then(() => console.log(".then: After dynamic import"));
print("After await dynamic import");
await test()
try {
    writeln("Count:", count(1, 4))
} catch (error) {
    console.error(error);
}
// ;

await import("./tests/__all__.js");

