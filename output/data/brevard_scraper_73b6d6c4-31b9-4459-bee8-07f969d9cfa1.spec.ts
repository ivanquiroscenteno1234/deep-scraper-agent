
import { test } from '@playwright/test';
import { expect } from '@playwright/test';

test('brevard_scraper_2026-02-18', async ({ page, context }) => {
  
    // Navigate to URL
    await page.goto('https://vaclmweb1.brevardclerk.us/AcclaimWeb/search/SearchTypeName');

    // Click element
    await page.click('#btnButton');

    // Fill input field
    await page.fill('#SearchOnName', 'Lauren Homes');

    // Fill input field
    await page.fill('#RecordDateFrom', '01/01/1980');

    // Fill input field
    await page.fill('#RecordDateTo', '02/18/2026');

    // Click element
    await page.click('#btnSearch');

    // Click element
    await page.click('#NamesWin #frmSchTarget input[type='submit']');
});