#!/usr/bin/env node

const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("@playwright/test");

async function main() {
  const [backgroundInput] = process.argv.slice(2);
  if (!backgroundInput) {
    throw new Error("Usage: node scripts/render-social-assets.cjs <background.png>");
  }

  const root = path.resolve(__dirname, "..");
  const publicDir = path.join(root, "public");
  const background = fs.readFileSync(path.resolve(backgroundInput)).toString("base64");
  const browser = await chromium.launch({ headless: true });

  try {
    const card = await browser.newPage({ viewport: { width: 1200, height: 630 }, deviceScaleFactor: 1 });
    await card.setContent(`
      <!doctype html>
      <html lang="es">
        <head>
          <meta charset="utf-8">
          <style>
            * { box-sizing: border-box; }
            html, body { width: 1200px; height: 630px; margin: 0; overflow: hidden; }
            body {
              position: relative;
              background: #061f3b url("data:image/png;base64,${background}") center / cover no-repeat;
              color: #f7f0e3;
              font-family: "Noto Sans", "DejaVu Sans", sans-serif;
            }
            body::before {
              content: "";
              position: absolute;
              inset: 0;
              background:
                linear-gradient(90deg, rgba(3, 20, 39, .98) 0%, rgba(3, 20, 39, .92) 44%, rgba(3, 20, 39, .38) 72%, rgba(3, 20, 39, .08) 100%),
                linear-gradient(0deg, rgba(3, 20, 39, .45), transparent 32%);
            }
            .frame {
              position: absolute;
              inset: 42px;
              border: 1px solid rgba(217, 173, 85, .34);
              border-radius: 4px;
            }
            .content {
              position: relative;
              width: 720px;
              height: 100%;
              padding: 72px 0 58px 86px;
              display: flex;
              flex-direction: column;
            }
            .hebrew {
              margin: 0;
              color: #f7f0e3;
              font: 700 66px/1 "Noto Serif Hebrew", "DejaVu Serif", serif;
              direction: rtl;
              text-align: left;
            }
            .rebbe {
              margin: 10px 0 0;
              color: #d9ad55;
              font: 700 22px/1.1 "Noto Sans", sans-serif;
              letter-spacing: .24em;
            }
            .rule {
              width: 92px;
              height: 3px;
              margin: 34px 0 26px;
              background: #b98a35;
            }
            h1 {
              margin: 0;
              color: #fffaf0;
              font: 600 55px/1.02 "DejaVu Serif", serif;
              letter-spacing: .035em;
            }
            .tagline {
              max-width: 610px;
              margin: 25px 0 0;
              color: #e7e0d5;
              font-size: 24px;
              line-height: 1.35;
              letter-spacing: .005em;
            }
            .collaboration {
              margin: auto 0 0;
              color: #c8bda9;
              font-size: 15px;
              letter-spacing: .035em;
            }
            .mark {
              position: absolute;
              right: 76px;
              bottom: 60px;
              display: flex;
              align-items: center;
              gap: 10px;
              color: #f7f0e3;
              font-size: 13px;
              font-weight: 700;
              letter-spacing: .15em;
            }
            .mark span {
              display: grid;
              width: 34px;
              height: 34px;
              place-items: center;
              border: 1px solid #b98a35;
              border-radius: 8px;
              color: #d9ad55;
              font: 700 23px/1 "Noto Serif Hebrew", serif;
            }
          </style>
        </head>
        <body>
          <div class="frame"></div>
          <main class="content">
            <p class="hebrew" lang="he">רבי נחמן</p>
            <p class="rebbe">REBE NAJMÁN</p>
            <div class="rule"></div>
            <h1>BRESLOV<br>RESEARCH</h1>
            <p class="tagline">Investigación profunda sobre fuentes Breslov<br>en español, inglés y hebreo</p>
            <p class="collaboration">En colaboración con Breslov Research Institute — BRI</p>
          </main>
          <div class="mark"><span lang="he">נ</span> FUENTES VERIFICABLES</div>
        </body>
      </html>
    `, { waitUntil: "load" });
    await card.screenshot({
      path: path.join(publicDir, "images", "breslov-social-card.png"),
      type: "png",
    });

    const favicon = fs.readFileSync(path.join(publicDir, "favicon.svg")).toString("base64");
    for (const [size, name] of [[16, "favicon-16x16.png"], [32, "favicon-32x32.png"], [180, "apple-touch-icon.png"]]) {
      const page = await browser.newPage({ viewport: { width: size, height: size }, deviceScaleFactor: 1 });
      await page.setContent(`
        <!doctype html>
        <style>html,body{width:${size}px;height:${size}px;margin:0;overflow:hidden;background:transparent}img{display:block;width:${size}px;height:${size}px}</style>
        <img src="data:image/svg+xml;base64,${favicon}">
      `, { waitUntil: "load" });
      await page.screenshot({
        path: path.join(publicDir, name),
        type: "png",
        omitBackground: true,
      });
      await page.close();
    }
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
