// Builds the page twice:
//   public/          the real site, served by the Worker (talks to /api, no answers inside)
//   dist/prototype.html  one self-contained file that runs the game on the sample pack
import { build } from "esbuild";
import { copyFileSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";

mkdirSync("public", { recursive: true });
mkdirSync("dist", { recursive: true });
const template = readFileSync("src/web/index.html", "utf8");
const css = readFileSync("src/web/style.css", "utf8");
const common = { bundle: true, minify: true, target: "es2020", legalComments: "none" };

await build({ ...common, entryPoints: ["src/web/main.ts"], format: "esm", outfile: "public/app.js" });
copyFileSync("src/web/style.css", "public/style.css");
writeFileSync("public/index.html", template
  .replace("<!--STYLE-->", () => '<link rel="stylesheet" href="/style.css">')
  .replace("<!--SCRIPT-->", () => '<script type="module" src="/app.js"></script>'));

const proto = await build({ ...common, entryPoints: ["src/web/prototype.ts"], format: "iife", write: false });
const js = proto.outputFiles[0].text.replace(/<\/(script)/gi, "<\\/$1");
// replacer functions, so "$" in the minified code is never read as a pattern
writeFileSync("dist/prototype.html", template
  .replace("<title>CS-Krillion</title>", () => "<title>CS-Krillion Prototype</title>")
  .replace("<!--STYLE-->", () => `<style>\n${css}</style>`)
  .replace("<!--SCRIPT-->", () => `<script>${js}</script>`));

const kb = (f) => (Buffer.byteLength(readFileSync(f)) / 1024).toFixed(0);
console.log(`public/app.js ${kb("public/app.js")} KB, dist/prototype.html ${kb("dist/prototype.html")} KB`);
