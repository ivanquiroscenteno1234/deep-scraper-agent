
import { test } from '@playwright/test';
import { expect } from '@playwright/test';

test('www_scraper_2026-01-18', async ({ page, context }) => {
  
    // Navigate to URL
    await page.goto('https://www.tccsearch.org/RealEstate/SearchEntry.aspx');

    // Click element
    await page.click('#cph1_lnkAccept');

    // Fill input field
    await page.fill('#cphNoMargin_f_txtParty', 'SMITH & ARMSTRONG INC');

    // Fill input field
    await page.fill('#cphNoMargin_f_ddcDateFiledFrom input', '01/01/2006');

    // Fill input field
    await page.fill('#cphNoMargin_f_ddcDateFiledTo input', '12/31/2006');

    // Click element
    await page.click('#cphNoMargin_SearchButtons1_btnSearch');
});