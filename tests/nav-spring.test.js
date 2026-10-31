import test from 'node:test';
import assert from 'node:assert/strict';
import {
  advanceNavSpring, isNavSpringSettled, navLensStretch, planNavMotion, sampleNavMotion
} from '../src/components/navSpring.js';

const move = (target, fps, duration = 1.2, initial = { position: 0, velocity: 0 }) => {
  let spring = initial;
  for (let step = 0; step < Math.round(fps * duration); step += 1) {
    spring = advanceNavSpring(spring, target, 1 / fps);
  }
  return spring;
};

test('lens settles at the target consistently on 30/60/120Hz displays', () => {
  const positions = [30, 60, 120].map(rate => move(220, rate));
  for (const value of positions) {
    assert.ok(isNavSpringSettled(value.position, value.velocity, 220));
    assert.ok(Math.abs(value.position - 220) < 0.01);
  }
  assert.ok(Math.max(...positions.map(p => p.position)) -
    Math.min(...positions.map(p => p.position)) < 0.05);
});

test('new taps reverse an in-flight spring rather than restarting it', () => {
  const moving = move(220, 60, 0.2);
  assert.ok(moving.velocity > 0);
  const reversed = advanceNavSpring(moving, 35, 1 / 60);
  assert.ok(reversed.position > 0);
  assert.notEqual(reversed.position, 35);
  const final = move(35, 60, 1.2, reversed);
  assert.ok(isNavSpringSettled(final.position, final.velocity, 35));
});

test('large frame gaps are capped so resumed tabs cannot explode', () => {
  const value = advanceNavSpring({ position: 0, velocity: 0 }, 200, 12);
  assert.ok(value.position > 0 && value.position < 200);
  assert.ok(Number.isFinite(value.velocity));
});

test('the glass stretch is bounded and disappears when settled', () => {
  assert.equal(navLensStretch(0, 200), 1);
  assert.equal(navLensStretch(800, 0), 1);
  assert.equal(navLensStretch(Number.NaN, 500), 1);
  assert.ok(navLensStretch(1200, 100) > 1);
  assert.ok(navLensStretch(9000, 2000) <= 1.16);
});

test('native motion preserves position and velocity when a tap interrupts it', () => {
  const motion = planNavMotion({ position: 7, velocity: 0 }, 220);
  const interrupted = sampleNavMotion(motion, 125);
  assert.ok(interrupted.position > 7 && interrupted.position < 220);
  assert.ok(interrupted.velocity > 0);
  const reversed = planNavMotion(interrupted, 35);
  assert.deepEqual(reversed.samples[0], interrupted);
  assert.deepEqual(sampleNavMotion(reversed, reversed.duration), { position: 35, velocity: 0 });
  assert.deepEqual(sampleNavMotion(reversed, reversed.duration + 5000), { position: 35, velocity: 0 });
  assert.ok(reversed.duration < 1000);
});
