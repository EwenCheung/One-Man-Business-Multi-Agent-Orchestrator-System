import { test, expect } from '@playwright/test';

test.describe('Owner Dashboard', () => {
  test('should login and navigate to dashboard', async ({ page }) => {
    await page.goto('/login');

    await page.fill('input[type="email"]', 'test@gmail.com');
    await page.fill('input[type="password"]', 'Abcd@1234');

    await page.click('button[type="submit"]');

    await page.waitForURL('/dashboard');

    await expect(page.getByRole('heading', { name: 'Dashboard', exact: true })).toBeVisible();
  });

  test('should navigate to Chat to Agent and load the UI', async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[type="email"]', 'test@gmail.com');
    await page.fill('input[type="password"]', 'Abcd@1234');
    await page.click('button[type="submit"]');
    await page.waitForURL('/dashboard');

    await page.click('text=Chat to Agent');
    await page.waitForURL('/chat');

    await expect(page.locator('h2').filter({ hasText: 'Chat to Agent' })).toBeVisible();
    await expect(page.locator('input[placeholder="Ask your agent anything..."]')).toBeVisible();
  });
});
