
import { test } from '@playwright/test';
import { expect } from '@playwright/test';

test('dallas_scraper_2026-01-20', async ({ page, context }) => {
  
    // Navigate to URL
    await page.goto('https://dallas.tx.publicsearch.us/');

    // Fill input field
    await page.fill('input[data-testid="searchInputBox"]', 'LA FITTE INV INC');

    // Fill input field
    await page.fill('input[aria-label="Starting Recorded Date"]', '01/01/1978');

    // Fill input field
    await page.fill('input[aria-label="Ending Recorded Date"]', '12/31/1978');

    // Click element
    await page.click('button[data-testid="searchSubmitButton"]');

    // Click element
    await page.click('button.popup__clear');
});