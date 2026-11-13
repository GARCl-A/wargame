// Starts Electron on this folder. An editor's terminal can set ELECTRON_RUN_AS_NODE, which makes Electron run
// main.js as plain Node (`require("electron").app` is then undefined), so it is dropped here.
"use strict";

const { spawn } = require("child_process");

const env = { ...process.env };
delete env.ELECTRON_RUN_AS_NODE;
const child = spawn(require("electron"), [".", ...process.argv.slice(2)], { stdio: "inherit", env, cwd: __dirname });
child.on("exit", code => process.exit(code ?? 1));
