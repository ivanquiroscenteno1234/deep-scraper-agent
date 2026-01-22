
import { test } from '@playwright/test';
import { expect } from '@playwright/test';

test('c_scraper_2026-01-20', async ({ page, context }) => {
  
    // Navigate to URL
    await page.goto('https://www.cclerk.hctx.net/Applications/WebSearch/RP.aspx');

    // Fill input field
    await page.fill('#ctl00_ContentPlaceHolder1_txtOR', 'CENTEX HOMES ETAL');

    // Fill input field
    await page.fill('#ctl00_ContentPlaceHolder1_txtFrom', '07/06/2006');

    // Fill input field
    await page.fill('#ctl00_ContentPlaceHolder1_txtTo', '07/06/2006');

    // Click element
    await page.click('#ctl00_ContentPlaceHolder1_btnSearch');
});