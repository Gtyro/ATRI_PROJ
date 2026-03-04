import fs from "node:fs";
import path from "node:path";

const projectRoot = process.cwd();

const requiredFiles = [
  "tsconfig.json",
  "src/main.ts",
  "src/router/index.ts",
  "src/utils/jwt.ts",
  "src/types/module_metrics.ts",
  "src/views/wordcloud/config.ts",
  "src/views/dashboard/index.ts",
  "src/views/dashboard/components/botInfo/index.ts",
  "src/views/dashboard/components/SystemInfoPanel/index.ts",
  "src/views/dashboard/components/chatInfo/index.ts",
  "src/api/index.ts",
  "src/api/auth.ts",
  "src/api/db.ts",
  "src/api/memory.ts",
  "src/api/dashboard.ts",
  "src/api/wordcloud.ts",
  "src/api/plugin_policy.ts",
  "src/api/module_metrics.ts",
  "src/api/contracts/module_metrics.ts",
  "src/stores/auth.ts",
  "src/stores/db.ts",
  "src/stores/memory.ts",
  "src/stores/index.ts",
];

const forbiddenLegacyFiles = [
  "src/main.js",
  "src/router/index.js",
  "src/utils/jwt.js",
  "src/views/wordcloud/config.js",
  "src/views/dashboard/index.js",
  "src/views/dashboard/components/botInfo/index.js",
  "src/views/dashboard/components/SystemInfoPanel/index.js",
  "src/views/dashboard/components/chatInfo/index.js",
  "src/api/index.js",
  "src/api/auth.js",
  "src/api/db.js",
  "src/api/memory.js",
  "src/api/dashboard.js",
  "src/api/wordcloud.js",
  "src/api/plugin_policy.js",
  "src/api/module_metrics.js",
  "src/api/contracts/module_metrics.js",
  "src/stores/auth.js",
  "src/stores/db.js",
  "src/stores/memory.js",
  "src/stores/index.js",
];

const missing = requiredFiles.filter(
  (relativePath) => !fs.existsSync(path.join(projectRoot, relativePath)),
);

const legacyLeftovers = forbiddenLegacyFiles.filter((relativePath) =>
  fs.existsSync(path.join(projectRoot, relativePath)),
);

const tsconfigPath = path.join(projectRoot, "tsconfig.json");
let tsconfigErrors = [];
if (fs.existsSync(tsconfigPath)) {
  try {
    const parsed = JSON.parse(fs.readFileSync(tsconfigPath, "utf8"));
    const compilerOptions = parsed.compilerOptions || {};

    if (compilerOptions.strict !== true) {
      tsconfigErrors.push("compilerOptions.strict must be true");
    }

    if (compilerOptions.noImplicitOverride !== true) {
      tsconfigErrors.push("compilerOptions.noImplicitOverride must be true");
    }

    if (compilerOptions.noUncheckedIndexedAccess !== true) {
      tsconfigErrors.push(
        "compilerOptions.noUncheckedIndexedAccess must be true",
      );
    }

    if (!compilerOptions.paths || !compilerOptions.paths["@/*"]) {
      tsconfigErrors.push("compilerOptions.paths['@/*'] must be configured");
    }
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error);
    tsconfigErrors.push(`tsconfig parse failed: ${reason}`);
  }
}

const collectJsFiles = (directory) => {
  const absoluteDirectory = path.join(projectRoot, directory);
  if (!fs.existsSync(absoluteDirectory)) {
    return [];
  }

  const result = [];
  const stack = [absoluteDirectory];

  while (stack.length) {
    const current = stack.pop();
    if (!current) {
      continue;
    }

    const entries = fs.readdirSync(current, { withFileTypes: true });
    for (const entry of entries) {
      const absolutePath = path.join(current, entry.name);
      if (entry.isDirectory()) {
        stack.push(absolutePath);
        continue;
      }
      if (entry.isFile() && absolutePath.endsWith(".js")) {
        result.push(path.relative(projectRoot, absolutePath));
      }
    }
  }

  return result.sort();
};

const jsFilesInSrc = collectJsFiles("src");

if (
  missing.length ||
  legacyLeftovers.length ||
  tsconfigErrors.length ||
  jsFilesInSrc.length
) {
  console.error("[type-governance] validation failed");

  if (missing.length) {
    console.error("- missing required files:");
    for (const file of missing) {
      console.error(`  - ${file}`);
    }
  }

  if (legacyLeftovers.length) {
    console.error("- legacy JS files still exist:");
    for (const file of legacyLeftovers) {
      console.error(`  - ${file}`);
    }
  }

  if (tsconfigErrors.length) {
    console.error("- tsconfig issues:");
    for (const issue of tsconfigErrors) {
      console.error(`  - ${issue}`);
    }
  }

  if (jsFilesInSrc.length) {
    console.error("- .js files still exist in src:");
    for (const file of jsFilesInSrc) {
      console.error(`  - ${file}`);
    }
  }

  process.exit(1);
}

console.log("[type-governance] ok");
