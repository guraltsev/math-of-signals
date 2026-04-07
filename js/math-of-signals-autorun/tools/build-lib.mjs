import { copyFile, mkdir } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';

const source = resolve('src/index.js');
const destination = resolve('lib/index.js');

await mkdir(dirname(destination), { recursive: true });
await copyFile(source, destination);
