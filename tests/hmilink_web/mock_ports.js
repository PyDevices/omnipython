// SPDX-FileCopyrightText: 2026 Brad Barnett
//
// SPDX-License-Identifier: MIT

// Stand-ins for navigator.serial and navigator.bluetooth whose far end is the
// test's Python process. Every few milliseconds each port calls
// window.hostXfer(channel, bytesOut) and gets back the bytes the host has for
// it, so a CPython device or panel sits where the board would.
//
// The Bluetooth one is a board serving the Nordic UART service: it notifies
// in MTU - 3 sized pieces and, as Android does, cuts a longer write short
// without saying so. ?plant=1 turns every "0.75" into "0.15" both ways,
// which every check must catch.
(() => {
  const q = new URLSearchParams(location.search);
  const PLANT = q.get("plant") === "1";
  const MTU = parseInt(q.get("mock_mtu") || "247", 10);
  const encoder = new TextEncoder();
  const decoder = new TextDecoder();

  const tamper = (bytes) => {
    if (!PLANT || !bytes.length) return bytes;
    return encoder.encode(decoder.decode(bytes).split("0.75").join("0.15"));
  };

  // One host channel: bytes queued for the host, and a callback for what
  // comes back.
  function channel(name, deliver) {
    let out = [];
    let stopped = false;
    const tick = async () => {
      if (stopped) return;
      const sent = out;
      out = [];
      try {
        const back = await window.hostXfer(name, Array.from(tamper(new Uint8Array(sent))));
        if (back && back.length) deliver(tamper(new Uint8Array(back)));
      } catch (e) {
        window.gateLog("HOST ERROR " + e);
      }
      setTimeout(tick, 5);
    };
    setTimeout(tick, 5);
    return {
      send: (bytes) => { for (const b of bytes) out.push(b); },
      stop: () => { stopped = true; },
    };
  }

  // -- WebSerial --

  class MockSerialPort {
    async open() {
      let controller;
      this.readable = new ReadableStream({ start: (c) => { controller = c; } });
      const link = channel("serial", (bytes) => controller.enqueue(bytes));
      this.writable = new WritableStream({ write: (chunk) => link.send(chunk) });
      this._link = link;
    }
    getInfo() { return { usbVendorId: 0x303a, usbProductId: 0x1001 }; }
    async close() { this._link.stop(); }
  }

  window.mockSerial = {
    requestPort: async () => new MockSerialPort(),
  };

  // -- Web Bluetooth --

  const NUS = "6e400001-b5a3-f393-e0a9-e50e24dcca9e";
  const RX = "6e400002-b5a3-f393-e0a9-e50e24dcca9e";
  const TX = "6e400003-b5a3-f393-e0a9-e50e24dcca9e";

  class Char extends EventTarget {
    constructor(uuid, props) {
      super();
      this.uuid = uuid;
      this.properties = props;
      this.value = null;
    }
  }

  function makeDevice(name) {
    const device = new EventTarget();
    device.name = name;
    const tx = new Char(TX, { notify: true });
    const rx = new Char(RX, { write: true, writeWithoutResponse: true });
    let link = null;
    let subscribed = false;
    rx.writeValueWithoutResponse = async (v) => {
      if (!device.gatt.connected) throw Object.assign(new Error("GATT Server is disconnected."), { name: "NetworkError" });
      link.send(new Uint8Array(v).slice(0, MTU - 3));
    };
    rx.writeValueWithResponse = rx.writeValueWithoutResponse;
    tx.startNotifications = async () => { subscribed = true; return tx; };
    tx.stopNotifications = async () => { subscribed = false; return tx; };
    const notify = (bytes) => {
      for (let i = 0; i < bytes.length; i += MTU - 3) {
        if (!subscribed) continue; // lost, as on a radio
        const part = bytes.slice(i, i + MTU - 3);
        tx.value = new DataView(part.buffer);
        tx.dispatchEvent(new Event("characteristicvaluechanged"));
      }
    };
    const service = {
      uuid: NUS,
      getCharacteristic: async (uuid) => (uuid === RX ? rx : uuid === TX ? tx : Promise.reject(new Error("no " + uuid))),
    };
    device.gatt = {
      connected: false,
      connect: async () => {
        device.gatt.connected = true;
        link = channel("bluetooth", notify);
        return { getPrimaryService: async (uuid) => (uuid === NUS ? service : Promise.reject(new Error("no " + uuid))) };
      },
      disconnect: () => {
        if (!device.gatt.connected) return;
        device.gatt.connected = false;
        link.stop();
        device.dispatchEvent(new Event("gattserverdisconnected"));
      },
    };
    return device;
  }

  window.mockBluetooth = {
    requestDevice: async (options) => {
      const filter = (options.filters || [])[0] || {};
      if (!filter.name && !(filter.services || []).includes(NUS)) throw new Error("the chooser has nothing to offer");
      return makeDevice(filter.name || "board");
    },
  };
})();
