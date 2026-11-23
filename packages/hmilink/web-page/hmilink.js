// SPDX-FileCopyrightText: 2026 Brad Barnett
//
// SPDX-License-Identifier: MIT

// hmilink on a web page: a board over WebSerial or Web Bluetooth.
//
// Open a port from a click (the browser asks which device), then either
// speak hmilink from JavaScript with a Link, or hand the port to Python
// running in the page (MicroPython's WebAssembly build, or Pyodide), which
// wraps it with hmilink.web.stream():
//
//   import { openSerial, openBluetooth, Link } from "./hmilink.js";
//   const port = await openBluetooth({ name: "rack", mtu: 247 });
//   const link = new Link(port);
//   link.onmessage = (msg) => console.log(msg.t, msg);
//   link.send({ t: "op", op: "replace", path: "/k", value: 1, id: 1 });
//
// Frames are one JSON message per line, as hmilink.stream sends them over a
// UART, so the board's side is stream.link() on a UART or USB CDC, or
// hmilink.ble on its radio.

// Nordic UART service: the central writes RX and the peripheral notifies TX.
export const NUS_SERVICE = "6e400001-b5a3-f393-e0a9-e50e24dcca9e";
export const NUS_RX = "6e400002-b5a3-f393-e0a9-e50e24dcca9e";
export const NUS_TX = "6e400003-b5a3-f393-e0a9-e50e24dcca9e";

// The bytes a page holds for a reader that has stopped reading. A port
// that fills closes, since a frame dropped from the middle can't be repaired.
export const IN_LIMIT = 1 << 20;

const encoder = new TextEncoder();

// A byte port. What arrives waits until read() or a Link takes it; what's
// sent goes out one write at a time, in order.
export class Port {
  constructor() {
    this.closed = false;
    this.error = null;
    this.onclose = null;
    this._in = [];
    this._inLength = 0;
    this._ondata = null;
    this._queue = [];
    this._sending = false;
  }

  // Bytes waiting to be read.
  get waiting() {
    return this._inLength;
  }

  // Up to n bytes as a Uint8Array, empty when nothing waits. Never waits.
  read(n) {
    const out = new Uint8Array(Math.min(n, this._inLength));
    let at = 0;
    while (at < out.length) {
      const chunk = this._in[0];
      const take = Math.min(chunk.length, out.length - at);
      out.set(chunk.subarray(0, take), at);
      at += take;
      if (take === chunk.length) this._in.shift();
      else this._in[0] = chunk.subarray(take);
    }
    this._inLength -= out.length;
    return out;
  }

  // Takes all of data (a string, sent as UTF-8, or bytes) and returns its
  // length in bytes, or takes none and returns 0 while an earlier write is
  // still going out. That is the shape hmilink.stream wants: a link that
  // hears 0 keeps its frames and offers them again.
  write(data) {
    if (this.closed) throw new Error("port closed");
    if (this._sending || this._queue.length) return 0;
    const bytes = typeof data === "string" ? encoder.encode(data) : new Uint8Array(data);
    this.send(bytes);
    return bytes.length;
  }

  // Queues bytes to go out after everything sent before them.
  send(bytes) {
    if (this.closed) throw new Error("port closed");
    this._queue.push(bytes);
    this._pump();
  }

  async close() {
    this._finish(null);
  }

  // -- for the transports

  _push(bytes) {
    if (this.closed || !bytes.length) return;
    if (this._ondata) {
      this._ondata(bytes);
      return;
    }
    if (this._inLength + bytes.length > IN_LIMIT) {
      this._finish(new Error("nothing read the port's input"));
      return;
    }
    this._in.push(bytes);
    this._inLength += bytes.length;
  }

  async _pump() {
    if (this._sending) return;
    this._sending = true;
    try {
      while (this._queue.length && !this.closed) {
        await this._write(this._queue.shift());
      }
    } catch (error) {
      this._finish(error);
    } finally {
      this._sending = false;
    }
  }

  async _write(_bytes) {
    throw new Error("a Port subclass writes");
  }

  _finish(error) {
    if (this.closed) return;
    this.closed = true;
    this.error = error;
    this._queue = [];
    this._teardown().catch(() => {});
    if (this.onclose) this.onclose(error);
  }

  async _teardown() {}
}

// A serial port through WebSerial: a board's USB CDC or a USB-serial chip.
export class SerialPort extends Port {
  constructor(port) {
    super();
    this.port = port;
    this.reader = null;
    this.writer = null;
  }

  async open(baudRate = 115200) {
    await this.port.open({ baudRate });
    this.writer = this.port.writable.getWriter();
    this.reader = this.port.readable.getReader();
    this._readLoop(this.reader);
    return this;
  }

  async _readLoop(reader) {
    try {
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        this._push(value);
      }
      this._finish(null);
    } catch (error) {
      // An unplugged device errors its stream rather than ending it.
      this._finish(error);
    }
  }

  async _write(bytes) {
    await this.writer.write(bytes);
  }

  async _teardown() {
    try { await this.reader?.cancel(); } catch (_e) { /* already errored */ }
    try { this.reader?.releaseLock(); } catch (_e) { /* already released */ }
    try { this.writer?.releaseLock(); } catch (_e) { /* already released */ }
    try { await this.port.close(); } catch (_e) { /* never opened, or gone */ }
  }
}

// A board's Nordic UART service through Web Bluetooth.
export class BluetoothPort extends Port {
  constructor(device, mtu = 23) {
    super();
    this.device = device;
    // The browser doesn't say what MTU it agreed, and a write longer than
    // the link carries can be cut short with no error, so writes are sized
    // to the MTU the page is told.
    this.chunk = mtu - 3;
    this.rx = null;
    this.tx = null;
    this._withoutResponse = false;
    this._ondisconnect = () => this._finish(new Error("the board disconnected"));
    this._onvalue = (event) => {
      const v = event.target.value;
      this._push(new Uint8Array(v.buffer.slice(v.byteOffset, v.byteOffset + v.byteLength)));
    };
  }

  async open() {
    this.device.addEventListener("gattserverdisconnected", this._ondisconnect);
    const server = await this.device.gatt.connect();
    const service = await server.getPrimaryService(NUS_SERVICE);
    this.rx = await service.getCharacteristic(NUS_RX);
    this.tx = await service.getCharacteristic(NUS_TX);
    this._withoutResponse = Boolean(this.rx.properties?.writeWithoutResponse);
    this.tx.addEventListener("characteristicvaluechanged", this._onvalue);
    await this.tx.startNotifications();
    // The board can't tell when a central has subscribed, so hmilink.ble
    // sends nothing until the central speaks: an empty line, which no
    // reader counts as a frame.
    this.send(encoder.encode("\n"));
    return this;
  }

  async _write(bytes) {
    for (let i = 0; i < bytes.length; i += this.chunk) {
      const part = bytes.slice(i, i + this.chunk);
      if (this._withoutResponse) await this.rx.writeValueWithoutResponse(part);
      else await this.rx.writeValueWithResponse(part);
    }
  }

  async _teardown() {
    this.device.removeEventListener("gattserverdisconnected", this._ondisconnect);
    this.tx?.removeEventListener("characteristicvaluechanged", this._onvalue);
    try { this.device.gatt.disconnect(); } catch (_e) { /* already gone */ }
  }
}

// Asks for a serial port and opens it. Call it from a click or a key press.
// options: baudRate (115200), filters (WebSerial's usbVendorId filters),
// serial (navigator.serial, or a stand-in for tests).
export async function openSerial(options = {}) {
  const serial = options.serial || navigator.serial;
  if (!serial) throw new Error("this browser has no WebSerial");
  const port = await serial.requestPort({ filters: options.filters || [] });
  return new SerialPort(port).open(options.baudRate || 115200);
}

// Asks for a board advertising the Nordic UART service and connects. Call
// it from a click or a key press. options: name (only a board with this
// name is offered), mtu (23; 247 for a board on bledev, which asks for it),
// bluetooth (navigator.bluetooth, or a stand-in for tests).
export async function openBluetooth(options = {}) {
  const bluetooth = options.bluetooth || navigator.bluetooth;
  if (!bluetooth) throw new Error("this browser has no Web Bluetooth");
  const filter = options.name ? { name: options.name } : { services: [NUS_SERVICE] };
  const device = await bluetooth.requestDevice({ filters: [filter], optionalServices: [NUS_SERVICE] });
  return new BluetoothPort(device, options.mtu || 23).open();
}

// hmilink's framing in JavaScript: one JSON message per line each way.
// Set onmessage before data arrives; a line that isn't JSON is counted in
// `bad` and skipped, as a device or panel does.
export class Link {
  constructor(port) {
    this.port = port;
    this.onmessage = null;
    this.onclose = null;
    this.bad = 0;
    this._text = "";
    this._decoder = new TextDecoder();
    port._ondata = (bytes) => this._feed(bytes);
    if (port.waiting) this._feed(port.read(port.waiting));
    port.onclose = (error) => this.onclose && this.onclose(error);
  }

  get closed() {
    return this.port.closed;
  }

  send(msg) {
    const text = typeof msg === "string" ? msg : JSON.stringify(msg);
    this.port.send(encoder.encode(text + "\n"));
  }

  close() {
    return this.port.close();
  }

  _feed(bytes) {
    this._text += this._decoder.decode(bytes, { stream: true });
    let i;
    while ((i = this._text.indexOf("\n")) >= 0) {
      let line = this._text.slice(0, i);
      this._text = this._text.slice(i + 1);
      if (line.endsWith("\r")) line = line.slice(0, -1);
      if (!line) continue;
      let msg;
      try {
        msg = JSON.parse(line);
      } catch (_e) {
        this.bad++;
        continue;
      }
      if (this.onmessage) this.onmessage(msg);
    }
  }
}
