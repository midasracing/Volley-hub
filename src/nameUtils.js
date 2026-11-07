import { normalizeName } from './data.js';

export const sameName = (a, b) => normalizeName(a) === normalizeName(b);
