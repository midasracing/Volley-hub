import { mkdir, copyFile, readdir } from 'node:fs/promises';
import { resolve, join } from 'node:path';

const root = resolve(import.meta.dirname, '..');
const source = join(root, 'data');
const destination = join(root, 'public', 'data');
await mkdir(destination, { recursive: true });
const names = (await readdir(source)).filter(name => name.endsWith('.json'));
await Promise.all(names.map(name => copyFile(join(source, name), join(destination, name))));
console.log('Copied ' + names.length + ' up-to-date league data files to public/data.');
