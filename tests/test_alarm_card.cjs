"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

const source = fs.readFileSync(path.join(__dirname, "..", "www", "tenmicron-alarm-card.js"), "utf8");
const registry = new Map();
class FakeNode {
  constructor() { this.textContent = ""; this.className = ""; this.hidden = true; this.disabled = false; }
  addEventListener(_name, cb) { this.callback = cb; }
}
class FakeElement {
  constructor() { this.isConnected = false; this.nodes = new Map(); }
  attachShadow() {
    this.shadowRoot = {
      innerHTML: "",
      getElementById: (id) => {
        if (!this.nodes.has(id)) this.nodes.set(id, new FakeNode());
        return this.nodes.get(id);
      }
    };
    return this.shadowRoot;
  }
}
const context = {
  window: { customCards: [] },
  customElements: { get: (key) => registry.get(key), define: (key, value) => registry.set(key, value) },
  HTMLElement: FakeElement,
  setInterval, clearInterval, setTimeout, clearTimeout,
};
vm.runInNewContext(source, context, { filename: "tenmicron-alarm-card.js" });
const Card = registry.get("tenmicron-alarm-card");

test("registered as a custom Lovelace card", () => {
  assert.equal(typeof Card, "function");
  assert.equal(context.window.customCards[0].type, "tenmicron-alarm-card");
});

test("requires a binary sensor entity", () => {
  const c = new Card();
  assert.throws(() => c.setConfig({ entity: "sensor.mount" }), /binary_sensor/);
});

test("does not ring on historic initial ON, rings only on later OFF to ON", () => {
  const c = new Card(); c.isConnected = true;
  c.setConfig({ entity: "binary_sensor.test" }); c.connectedCallback();
  const rings = []; c._tone = (testMode) => rings.push(testMode);
  c._armed = true;
  c.hass = { language: "cs", states: { "binary_sensor.test": { state: "on" } } };
  assert.deepEqual(rings, []);
  c.hass = { language: "cs", states: { "binary_sensor.test": { state: "off" } } };
  c.hass = { language: "cs", states: { "binary_sensor.test": { state: "on" } } };
  assert.deepEqual(rings, [false]);
  assert.match(c.shadowRoot.getElementById("state").textContent, /ALARM/);
  assert.match(c.shadowRoot.getElementById("title").textContent, /alarm sledování/);
});

test("silenced alarm does not ring again until sensor returns to OFF", () => {
  const c = new Card(); c.isConnected = true;
  c.setConfig({ entity: "binary_sensor.test" }); c.connectedCallback();
  const rings = []; c._tone = (testMode) => rings.push(testMode);
  c._armed = true;
  c.hass = { language: "en", states: { "binary_sensor.test": { state: "off" } } };
  c.hass = { language: "en", states: { "binary_sensor.test": { state: "on" } } };
  c.shadowRoot.getElementById("silence").callback();
  c.hass = { language: "en", states: { "binary_sensor.test": { state: "on" } } };
  assert.deepEqual(rings, [false]);
  c.hass = { language: "en", states: { "binary_sensor.test": { state: "off" } } };
  c.hass = { language: "en", states: { "binary_sensor.test": { state: "on" } } };
  assert.deepEqual(rings, [false, false]);
});

test("unavailable never rings and does not assert a clear state", () => {
  const c = new Card(); c.isConnected = true;
  c.setConfig({ entity: "binary_sensor.test" }); c.connectedCallback();
  let calls = 0; c._tone = () => { calls += 1; };
  c._armed = true;
  c.hass = { language: "en", states: { "binary_sensor.test": { state: "unavailable" } } };
  c.hass = { language: "en", states: { "binary_sensor.test": { state: "on" } } };
  assert.equal(calls, 0);
});

test("card does not call Home Assistant services or mount commands", () => {
  assert.doesNotMatch(source, /hass\.callService|fetch\s*\(|WebSocket\s*\(/);
  assert.doesNotMatch(source, /:PsX#|:SUDT|:NUtim/);
});
