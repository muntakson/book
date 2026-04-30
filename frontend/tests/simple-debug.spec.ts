import { test, expect } from '@playwright/test';

test('Simple Debug - Check Bob Project State', async ({ page }) => {
  // Login
  await page.goto('http://localhost:8080');
  await page.fill('input[type="text"]', 'bob');
  await page.fill('input[type="password"]', 'q1');
  await page.click('button:has-text("Login")');

  // Wait for login
  await page.waitForTimeout(2000);

  // Take screenshot of project list
  await page.screenshot({ path: 'bob-project-list.png', fullPage: true });
  console.log('Screenshot 1: Project list saved');

  // Click on first project
  const projectCard = page.locator('.project-card').first();
  await projectCard.locator('button:has-text("View")').click();

  // Wait for detail page to load
  await page.waitForTimeout(2000);

  // Take screenshot of project detail
  await page.screenshot({ path: 'bob-project-detail.png', fullPage: true });
  console.log('Screenshot 2: Project detail saved');

  // Log all text content
  const bodyText = await page.locator('body').textContent();
  console.log('\n=== PAGE TEXT INCLUDES ===');
  console.log('Has "1단계":', bodyText?.includes('1단계'));
  console.log('Has "Proceed":', bodyText?.includes('Proceed'));
  console.log('Has "책 집필 계획":', bodyText?.includes('책 집필 계획'));

  // Check for buttons
  const buttons = await page.locator('button').allTextContents();
  console.log('\n=== ALL BUTTONS ON PAGE ===');
  buttons.forEach((btn, idx) => {
    console.log(`Button ${idx + 1}: "${btn}"`);
  });

  // Look specifically for proceed button
  const proceedButton = page.locator('button:has-text("Proceed to Stage 2")');
  const proceedButtonCount = await proceedButton.count();
  console.log(`\n=== PROCEED BUTTON ===`);
  console.log(`Found ${proceedButtonCount} "Proceed to Stage 2" button(s)`);

  if (proceedButtonCount > 0) {
    const isVisible = await proceedButton.isVisible();
    console.log(`Button visible: ${isVisible}`);
  }

  // Check for any proceed-related elements
  const proceedSection = page.locator('.proceed-section');
  const proceedSectionCount = await proceedSection.count();
  console.log(`\nFound ${proceedSectionCount} ".proceed-section" element(s)`);

  // Check stage indicators
  const stageText = page.locator('text=📍 Current Stage');
  const stageCount = await stageText.count();
  console.log(`Found ${stageCount} "Current Stage" indicator(s)`);

  if (stageCount > 0) {
    const stageContent = await stageText.textContent();
    console.log(`Stage content: "${stageContent}"`);
  }
});
