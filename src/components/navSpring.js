// One interruptible, frame-rate-independent spring for the liquid nav lens.
// No DOM dependencies: keep the physics easy to test in Node.
export const NAV_SPRING = Object.freeze({
  stiffness: 455,
  damping: 34,
  mass: 1
});

export function advanceNavSpring({ position, velocity }, target, elapsedSeconds) {
  if (![position, velocity, target, elapsedSeconds].every(Number.isFinite)) {
    return { position: target, velocity: 0 };
  }
  // A capped timestep + substeps prevents a hitch from launching the lens
  // offscreen after the tab has been backgrounded.
  const seconds = Math.min(Math.max(elapsedSeconds, 0), 0.04);
  const iterations = Math.max(1, Math.ceil(seconds / (1 / 120)));
  const dt = seconds / iterations;
  for (let step = 0; step < iterations; step += 1) {
    const force = NAV_SPRING.stiffness * (target - position);
    const friction = NAV_SPRING.damping * velocity;
    velocity += (force - friction) / NAV_SPRING.mass * dt;
    position += velocity * dt;
  }
  return { position, velocity };
}

export function isNavSpringSettled(position, velocity, target) {
  return Math.abs(position - target) < 0.22 && Math.abs(velocity) < 2;
}

// The moving glass briefly stretches in the direction of travel, and
// returns to its original proportions as velocity and distance approach zero.
export function navLensStretch(velocity, distanceToTarget) {
  if (!Number.isFinite(velocity) || !Number.isFinite(distanceToTarget)) return 1;
  const bySpeed = Math.abs(velocity) / 6700;
  const nearTarget = Math.abs(distanceToTarget) / 330;
  return 1 + Math.min(0.16, bySpeed, nearTarget);
}

// Precompute once per tap. Web Animations can then play these transforms on
// the compositor even while React is mounting a tab on the main thread.
export function planNavMotion(state, target) {
  const samples = [{ position: state.position, velocity: state.velocity }];
  let next = state;
  for (let frame = 0; frame < 120; frame += 1) {
    next = advanceNavSpring(next, target, 1 / 60);
    if (isNavSpringSettled(next.position, next.velocity, target)) {
      samples.push({ position: target, velocity: 0 });
      break;
    }
    samples.push(next);
  }
  return { samples, duration: (samples.length - 1) * 1000 / 60 };
}

export function sampleNavMotion(motion, elapsedMs) {
  const index = Math.max(0, Math.min(motion.samples.length - 1, elapsedMs * 60 / 1000));
  const start = motion.samples[Math.floor(index)];
  const end = motion.samples[Math.ceil(index)];
  const fraction = index % 1;
  return {
    position: start.position + (end.position - start.position) * fraction,
    velocity: start.velocity + (end.velocity - start.velocity) * fraction
  };
}
