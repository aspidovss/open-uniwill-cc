"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const test = require("node:test");
const context = vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(__dirname, "../uwccd/web/temperature.js"), "utf8"), context);
const { temperatureColorAt, temperatureInsertPoint, temperatureAddPosition } = vm.runInContext(
  "({temperatureColorAt, temperatureInsertPoint, temperatureAddPosition})", context);
const plain = x => JSON.parse(JSON.stringify(x));

test("new points sample the actual linear-light palette", () => {
  const points = [{ temp: 20, color: [0, 0, 0] }, { temp: 100, color: [255, 255, 255] }];
  assert.deepEqual(plain(temperatureColorAt(points, 60)), [188, 188, 188]);
  assert.deepEqual(plain(temperatureColorAt(points, 0)), [0, 0, 0]);
  assert.deepEqual(plain(temperatureColorAt(points, 120)), [255, 255, 255]);
  const added = plain(temperatureInsertPoint(points, 60));
  assert.deepEqual(added[1], { temp: 60, color: [188, 188, 188] });
  assert.equal(points.length, 2);
});
test("insertion preserves ordering, uniqueness and 15-point limit", () => {
  const points = [{ temp: 0, color: [255, 0, 0] }, { temp: 120, color: [0, 255, 0] }];
  assert.equal(temperatureInsertPoint(points, 0), null);
  assert.equal(temperatureInsertPoint(points, -1), null);
  const fifteen = Array.from({ length: 15 }, (_, i) => ({ temp: i * 8, color: [0, 0, 0] }));
  assert.equal(temperatureInsertPoint(fifteen, 119), null);
  assert.equal(temperatureAddPosition(points), 60);
  assert.equal(temperatureAddPosition([{ temp: 40 }, { temp: 95 }]), 67);
});
