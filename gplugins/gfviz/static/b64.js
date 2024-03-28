const readFileSync = require("fs").readFileSync;
const wasmCode = readFileSync("./schemedit.wasm");
const encoded = Buffer.from(wasmCode, "binary").toString("base64");
console.log(encoded.slice(0, 10));
