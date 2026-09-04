import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

import test from "node:test";
import assert from "node:assert/strict";

const packagePath = fileURLToPath(new URL("../package.json", import.meta.url));

test("the default Node test script is portable across Windows and POSIX shells", async () => {
  const packageJson = JSON.parse(await readFile(packagePath, "utf8"));
  const script = packageJson.scripts.test;

  assert.match(script, /^node --test(?: |$)/);
  assert.doesNotMatch(script, /[*?]/);
  assert.match(script, /tests(?:\\|\/)\S+/);
});
