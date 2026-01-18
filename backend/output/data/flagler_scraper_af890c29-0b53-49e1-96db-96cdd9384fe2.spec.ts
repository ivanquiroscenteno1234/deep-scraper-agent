
import { test } from '@playwright/test';
import { expect } from '@playwright/test';

test('flagler_scraper_2026-01-18', async ({ page, context }) => {
  
    // Navigate to URL
    await page.goto('https://records.flaglerclerk.com/');

    // Click element
    await page.click('a[title='Name Search']');

    // Click element
    await page.click('#idAcceptYes');

    // Fill input field
    await page.fill('input#name-Name', 'ESSEX HOME MORTGAGE SERVICING CORP');

    // Click element
    await page.click('a#submit-Name');

    // Click element
    await page.click('#idAcceptYes');
});