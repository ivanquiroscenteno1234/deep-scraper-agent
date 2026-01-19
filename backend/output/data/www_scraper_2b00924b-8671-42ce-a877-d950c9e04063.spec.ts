
import { test } from '@playwright/test';
import { expect } from '@playwright/test';

test('www_scraper_2026-01-19', async ({ page, context }) => {
  
    // Navigate to URL
    await page.goto('https://www.tccsearch.org/RealEstate/SearchEntry.aspx');

    // Click element
    await page.click('#cph1_lnkAccept');

    // Click element
    await page.click('#cphNoMargin_f_txtParty');

    // Click element
    await page.click('#cphNoMargin_f_ddcDateFiledFrom input');

    // Click element
    await page.click('#cphNoMargin_f_ddcDateFiledTo input');

    // Click element
    await page.click('#cphNoMargin_SearchButtons1_btnSearch');
});