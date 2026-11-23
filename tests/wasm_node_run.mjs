// SPDX-FileCopyrightText: 2026 Brad Barnett
//
// SPDX-License-Identifier: MIT
//
// Runs one of the plain-script checks in tests/ on the MicroPython WebAssembly
// build under node, the way the browser runs it:
//
//   node wasm_node_run.mjs MICROPYTHON_MJS ADAFRUIT_MIDI_DIR SCRIPT [--arg ...]
//
// lib/, packages/midiports/ and tests/ are copied into the build's own file
// system. SCRIPT is either a check file with a ``TESTS`` list of coroutine
// functions taking an ``Air`` (bledev_contract.py, midiports_ble_checks.py),
// which are awaited one at a time because the build has no ``asyncio.run``
// (the page's event loop drives asyncio), or a script that runs itself
// (midiports_contract.py, bledev_midi_codec.py); the second kind is named
// with ``--plain``. ``--adafruit`` is added for the scripts that take it.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const [mjs, adafruit, script, ...flags] = process.argv.slice(2);
const plain = flags.includes("--plain");
const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const { loadMicroPython } = await import(path.resolve(mjs));
const mp = await loadMicroPython({
  stdout: (line) => console.log(line),
  stderr: (line) => console.log("ERR " + line),
  linebuffer: true,
  heapsize: 32 * 1024 * 1024,
});

function put(from, to) {
  mp.FS.mkdirTree(to);
  for (const entry of fs.readdirSync(from, { withFileTypes: true })) {
    const source = path.join(from, entry.name);
    const target = to + "/" + entry.name;
    if (entry.isDirectory()) {
      if (entry.name !== "__pycache__") put(source, target);
    } else if (/\.(py|json)$/.test(entry.name)) {
      mp.FS.writeFile(target, fs.readFileSync(source));
    }
  }
}
put(path.join(repo, "lib"), "/w/lib");
put(path.join(repo, "packages", "midiports"), "/w/packages/midiports");
put(path.join(repo, "tests"), "/w/tests");
put(adafruit, "/w/adafruit/adafruit_midi");

const useAdafruit = /midiports_/.test(script);
if (plain) {
  const argv = JSON.stringify(["/w/tests/" + script].concat(useAdafruit ? ["--adafruit=/w/adafruit"] : []));
  await mp.runPythonAsync(`import sys
sys.path.insert(0, "/w/tests")
source = open("/w/tests/${script}").read().replace("sys.argv", "_ARGV")
scope = {"__name__": "__main__", "__file__": "/w/tests/${script}", "_ARGV": ${argv}}
try:
    exec(compile(source, "${script}", "exec"), scope)
except SystemExit as exit_:
    print("EXIT", exit_.args)
`);
} else {
  await mp.runPythonAsync(`import sys, asyncio
sys.path.insert(0, "/w/tests")
${useAdafruit ? 'sys.path.insert(0, "/w/adafruit")' : ""}
import ${script.replace(".py", "")} as checks
if hasattr(checks, "ADAFRUIT"):
    checks.ADAFRUIT = ${useAdafruit ? "True" : "False"}
failed = 0
for check in checks.TESTS:
    box = []

    async def one(check=check, box=box):
        try:
            await check(checks.Air())
        except Exception as error:  # noqa: BLE001
            box.append(error)
        else:
            box.append(None)

    task = asyncio.create_task(one())
    for _ in range(3000):
        if box:
            break
        await asyncio.sleep(0.01)
    else:
        task.cancel()
        box.append(Exception("hung for 30 s"))
    if box[0] is not None:
        failed += 1
        print("FAIL", check.__name__, "-", type(box[0]).__name__, box[0])
    else:
        print("PASS", check.__name__)
print("%d checks, %d failed (%s, wasm)" % (len(checks.TESTS), failed, sys.implementation.name))
`);
}
