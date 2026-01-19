
import { test } from '@playwright/test';
import { expect } from '@playwright/test';

test('brevard_scraper_2026-01-19', async ({ page, context }) => {
  
    // Navigate to URL
    await page.goto('https://vaclmweb1.brevardclerk.us/AcclaimWeb/search/SearchTypeName');
});