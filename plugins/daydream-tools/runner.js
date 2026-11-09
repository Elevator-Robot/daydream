import { spawn } from "node:child_process";
import { access, realpath } from "node:fs/promises";
import { constants } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

export async function resolveCheckout(entrypoint) {
  // OpenCode may preserve the installed symlink in import.meta.url.
  // Resolve the file itself before walking up to the permanent checkout.
  const file = await realpath(fileURLToPath(entrypoint));
  return path.resolve(path.dirname(file), "../..");
}

export function errorResult(code, message, partial = false) {
  return { ok: false, status: "error", error: { code, message, retry: "no", partial_possible: partial,
    next: "Inspect dependencies and any partial new output before retrying; do not bypass a permission denial." } };
}

export function createRunner(checkout, options = {}, spawnProcess = spawn, surface = "native") {
  return async function run(project, request, signal) {
    if (signal?.aborted) return errorResult("cancelled", "Operation cancelled before execution");
    let input;
    try { input = JSON.stringify(request); }
    catch { return errorResult("invalid_input", "Request must be serializable JSON"); }
    if (Buffer.byteLength(input) > 1024 * 1024) return errorResult("invalid_input", "Request exceeds 1 MiB");
    const script = path.join(checkout, "scripts", "operations.py");
    try { await access(script, constants.R_OK); }
    catch { return errorResult("backend_missing", "Daydream backend script is missing or unreadable; check the installed plugin link and keep the checkout in place"); }
    let python = options.python;
    if (!python) {
      python = path.join(checkout, ".venv-sprites", "bin", "python");
      try { await access(python, constants.X_OK); } catch { python = "python3"; }
    }
    const partial = request.action === "call" && request.input?.apply === true;
    const outputLimit = request.op === 'dashboard.media' ? 12 * 1024 * 1024 : request.op === 'dashboard.catalog' ? 4 * 1024 * 1024 : 1024 * 1024;
    return await new Promise((resolve) => {
      let child, output = "", bytes = 0, settled = false, timeout, kill;
      const cleanup = () => { clearTimeout(timeout); signal?.removeEventListener("abort", aborted); };
      const finish = (result, terminate = false) => {
        if (settled) return;
        settled = true;
        cleanup();
        if (terminate && child) {
          child.kill("SIGTERM");
          kill = setTimeout(() => child.kill("SIGKILL"), 1000);
          kill.unref?.();
        }
        resolve(result);
      };
      const aborted = () => finish(errorResult("cancelled", "Operation cancelled; new output may be partial", partial), true);
      try {
        child = spawnProcess(python, [script, "--project", project, "rpc", surface === "review_ui" ? "--review-ui" : "--native"],
          { cwd: project, stdio: ["pipe", "pipe", "pipe"], shell: false });
      } catch (error) { finish(errorResult("dependency_missing", `Cannot start Python backend: ${error.message}`)); return; }
      timeout = setTimeout(() => finish(errorResult("timeout", "Python operation exceeded 120 seconds", partial), true), 120000);
      signal?.addEventListener("abort", aborted, { once: true });
      child.stdout.setEncoding("utf8");
      child.stdout.on("data", (chunk) => {
        if (settled) return;
        bytes += Buffer.byteLength(chunk);
        if (bytes > outputLimit) { finish(errorResult("output_limit", `Backend result exceeded ${outputLimit / (1024 * 1024)} MiB`, partial), true); return; }
        output += chunk;
      });
      // Never dump private backend logs/tracebacks into model results.
      child.stderr.resume();
      child.stdout.on("error", () => finish(errorResult("backend_error", "Could not read backend output", partial), true));
      child.stderr.on("error", () => finish(errorResult("backend_error", "Backend diagnostics stream failed", partial), true));
      child.stdin.on("error", () => finish(errorResult("backend_error", "Could not send backend request", partial), true));
      child.on("error", () => finish(errorResult("dependency_missing", "Cannot start Python backend; check Python/Pillow setup", partial)));
      child.on("close", (code) => {
        clearTimeout(kill);
        if (settled) return;
        try {
          const result = JSON.parse(output);
          if (!result || typeof result.ok !== "boolean" || typeof result.status !== "string" || (code !== 0 && result.ok)) throw new Error();
          finish(result);
        } catch { finish(errorResult("backend_protocol", "Backend did not return a valid structured result", partial)); }
      });
      child.stdin.end(input);
      if (signal?.aborted) aborted();
    });
  };
}
