"use strict";

const assert = require("node:assert/strict");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const { chromium } = require("playwright");

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage();
    const fixture = path.resolve(__dirname, "..", "fixtures", "synthetic-ats.html");
    const resume = path.resolve(__dirname, "..", "fixtures", "fictional-resume.txt");
    await page.goto(pathToFileURL(fixture).href);
    await page.getByLabel("Name").fill("Jordan Rivera");
    await page.getByLabel("Email").fill("jordan.rivera@example.test");
    await page.getByLabel("Location").selectOption("Remote");
    await page.getByRole("button", { name: "Continue" }).click();
    await page.getByLabel("Education").fill("Example State University");
    await page.getByLabel("Employment").fill("Northwind Community Lab");
    await page.getByLabel("Resume").setInputFiles(resume);
    assert.equal(await page.getByLabel("Resume").evaluate(input => input.files[0].name), "fictional-resume.txt");
    await page.getByRole("button", { name: "Continue" }).click();
    await page.getByLabel("Screening answer").fill("Verified fictional answer");
    assert.equal(await page.getByLabel("Unsupported disclosure").getAttribute("data-classification"), "USER_REQUIRED");
    assert.equal(await page.getByLabel("Unsupported disclosure").inputValue(), "");
    const submit = page.getByRole("button", { name: "Submit application" });
    assert.equal(await submit.isDisabled(), true);
    assert.equal(await page.evaluate(() => window.authorizeSyntheticApplication("WRONG")), false);
    assert.equal(await submit.isDisabled(), true);
    await page.getByLabel("Legal attestation").check();
    assert.equal(await page.evaluate(() => window.authorizeSyntheticApplication("SYNTHETIC_APPROVED")), true);
    await submit.click();
    assert.equal(await page.locator("#confirmation").textContent(), "Application received SYNTHETIC-001");
    console.log(JSON.stringify({ uploaded: "fictional-resume.txt", unsupported: "stopped", approval_gate: "passed", confirmation: "SYNTHETIC-001" }));
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exit(1); });
