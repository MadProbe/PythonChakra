import './__impl__.js'; // precache
import './globals/__all__.js';
import './jsfunc/__all__.js';
import './Reflect/__all__.js';
import { type } from "../../package.json";
import { server } from "./example.toml";
print(type);
print(server);
