// demo:build: doctor -> seed -> capture -> render -> validate. Stops at the first failing stage.
import { execFileSync } from "node:child_process";
import path from "node:path";
import { TOOL_DIR } from "../pipeline/util.ts";

for (const stage of ["doctor", "seed", "capture", "render", "validate"]) {
  console.log(`\n== demo:${stage}`);
  execFileSync(process.execPath, [path.join(TOOL_DIR, "src/cli", `${stage}.ts`)], { stdio: "inherit", cwd: TOOL_DIR });
}
