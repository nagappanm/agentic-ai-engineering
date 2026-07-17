// Sample output of `npx playwright codegen http://127.0.0.1:8123/` — a recorded
// flow used to demo/test klew author_journey.py (record → journey). Not run directly.
import { test, expect } from '@playwright/test';

test('test', async ({ page }) => {
  await page.goto('http://127.0.0.1:8123/');
  await page.getByRole('textbox', { name: 'New todo' }).click();
  await page.getByRole('textbox', { name: 'New todo' }).fill('Write tests');
  await page.getByRole('textbox', { name: 'New todo' }).press('Enter');
  await page.getByRole('checkbox', { name: 'Toggle Write tests' }).check();
  await expect(page.getByTestId('todo-count')).toHaveText('0 items left');
});
