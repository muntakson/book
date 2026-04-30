import { test, expect } from '@playwright/test';

/**
 * Test workflow for Bob user (id=bob, pwd=q1)
 * Tests stages 1, 2, 3, and 4 of book creation process
 */

test.describe('Bob Book Creation Workflow', () => {
  // Increase timeout for long-running API operations
  test.setTimeout(300000); // 5 minutes

  let projectId: number;

  test.beforeEach(async ({ page }) => {
    // Navigate to app
    await page.goto('http://localhost:8080');
  });

  test('Stage 1: Login as Bob and create project', async ({ page }) => {
    // Login
    await page.fill('input[type="text"]', 'bob');
    await page.fill('input[type="password"]', 'q1');
    await page.click('button:has-text("Login")');

    // Wait for login to complete
    await expect(page.locator('text=👤 bob')).toBeVisible({ timeout: 10000 });
    console.log('✓ Logged in as Bob');

    // Navigate to create project
    await page.click('button:has-text("New Project")');
    await expect(page.locator('h2:has-text("Create New Project")')).toBeVisible();
    console.log('✓ Navigated to create project page');

    // Fill in project details
    const projectName = `Test Book ${Date.now()}`;
    await page.fill('input[placeholder*="Hydroponic"]', projectName);
    await page.fill('textarea[placeholder*="Describe your book"]',
      'A comprehensive guide to AI-powered greenhouse management with IoT sensors and digital twin technology.');

    // Create project
    await page.click('button:has-text("Create Project")');

    // Wait for redirect to list
    await expect(page.locator('h2:has-text("My Projects")')).toBeVisible({ timeout: 10000 });
    console.log('✓ Project created successfully');

    // Click on the newly created project
    await page.click(`text=${projectName}`);
    await expect(page.locator('h3:has-text("Book Idea")')).toBeVisible();
    console.log('✓ Project detail page opened');
  });

  test('Stage 1: Generate plan and verify Proceed button appears', async ({ page }) => {
    // Login
    await page.fill('input[type="text"]', 'bob');
    await page.fill('input[type="password"]', 'q1');
    await page.click('button:has-text("Login")');
    await expect(page.locator('text=👤 bob')).toBeVisible({ timeout: 10000 });

    // Get the first project
    await page.waitForSelector('.project-card', { timeout: 10000 });
    const projectCard = page.locator('.project-card').first();
    await projectCard.locator('button:has-text("View")').click();

    // Check if plan already generated
    const generateButton = page.locator('button:has-text("계획 생성하기")');
    if (await generateButton.isVisible()) {
      console.log('Generating plan...');
      await generateButton.click();

      // Wait for plan generation to complete (can take a while)
      await expect(page.locator('button:has-text("Copy")')).toBeVisible({ timeout: 120000 });
      console.log('✓ Plan generated successfully');
    } else {
      console.log('✓ Plan already exists');
    }

    // Verify we're at stage 1
    const stageIndicator = page.locator('text=📍 Current Stage: 1단계');
    await expect(stageIndicator).toBeVisible({ timeout: 5000 });
    console.log('✓ Stage 1 confirmed');

    // Look for the Proceed button
    const proceedButton = page.locator('button:has-text("Proceed to Stage 2")');

    // Debug: Check if button exists but might be hidden
    const buttonCount = await proceedButton.count();
    console.log(`Found ${buttonCount} proceed button(s)`);

    if (buttonCount === 0) {
      // Debug: Take a screenshot
      await page.screenshot({ path: 'debug-stage1.png', fullPage: true });
      console.log('Screenshot saved to debug-stage1.png');

      // Debug: Print current stage status
      const stageStatus = await page.locator('[class*="status-badge"]').allTextContents();
      console.log('Stage status badges:', stageStatus);

      // Debug: Check if there's any text about proceeding
      const bodyText = await page.locator('body').textContent();
      console.log('Body contains "Proceed":', bodyText?.includes('Proceed'));
      console.log('Body contains "stage":', bodyText?.includes('stage'));
      console.log('Body contains "1단계":', bodyText?.includes('1단계'));
    }

    // Assert the Proceed button is visible
    await expect(proceedButton).toBeVisible({ timeout: 5000 });
    console.log('✓ Proceed button is visible');
  });

  test('Full Workflow: Stages 1 → 2 → 3 → 4', async ({ page }) => {
    // Login
    await page.fill('input[type="text"]', 'bob');
    await page.fill('input[type="password"]', 'q1');
    await page.click('button:has-text("Login")');
    await expect(page.locator('text=👤 bob')).toBeVisible({ timeout: 10000 });
    console.log('✓ Logged in as Bob');

    // Get the first project
    await page.waitForSelector('.project-card', { timeout: 10000 });
    const projectCard = page.locator('.project-card').first();
    await projectCard.locator('button:has-text("View")').click();
    console.log('✓ Project opened');

    // Ensure plan is generated
    const generateButton = page.locator('button:has-text("계획 생성하기")');
    if (await generateButton.isVisible()) {
      await generateButton.click();
      await expect(page.locator('button:has-text("Copy")')).toBeVisible({ timeout: 120000 });
      console.log('✓ Plan generated');
    }

    // STAGE 1 → 2
    console.log('\n=== STAGE 1 → 2 ===');
    const stage1Proceed = page.locator('button:has-text("Proceed to Stage 2")');
    await expect(stage1Proceed).toBeVisible({ timeout: 10000 });

    // Click proceed with dialog confirmation
    page.once('dialog', dialog => {
      console.log('Dialog message:', dialog.message());
      dialog.accept();
    });
    await stage1Proceed.click();
    console.log('✓ Clicked Proceed to Stage 2');

    // Wait for stage 2 to start (check for logs section or stage indicator)
    await expect(page.locator('text=2단계').or(page.locator('text=Stage 2'))).toBeVisible({ timeout: 30000 });
    console.log('✓ Stage 2 started');

    // Wait for stage 2 to complete (look for stage 2 completed status)
    // This could take a LONG time depending on the backend
    console.log('Waiting for Stage 2 to complete (this may take several minutes)...');
    const stage2Complete = page.locator('text=Proceed to Stage 3').or(page.locator('button:has-text("Proceed to Stage 3")'));
    await expect(stage2Complete).toBeVisible({ timeout: 600000 }); // 10 minutes
    console.log('✓ Stage 2 completed');

    // STAGE 2 → 3
    console.log('\n=== STAGE 2 → 3 ===');
    const stage2Proceed = page.locator('button:has-text("Proceed to Stage 3")');
    await expect(stage2Proceed).toBeVisible({ timeout: 10000 });

    page.once('dialog', dialog => {
      console.log('Dialog message:', dialog.message());
      dialog.accept();
    });
    await stage2Proceed.click();
    console.log('✓ Clicked Proceed to Stage 3');

    // Wait for stage 3 to start
    await expect(page.locator('text=3단계').or(page.locator('text=Stage 3'))).toBeVisible({ timeout: 30000 });
    console.log('✓ Stage 3 started');

    // Wait for stage 3 to complete
    console.log('Waiting for Stage 3 to complete (fact-checking and review)...');
    const stage3Complete = page.locator('text=Proceed to Stage 4').or(page.locator('button:has-text("Proceed to Stage 4")'));
    await expect(stage3Complete).toBeVisible({ timeout: 600000 }); // 10 minutes
    console.log('✓ Stage 3 completed');

    // STAGE 3 → 4
    console.log('\n=== STAGE 3 → 4 ===');
    const stage3Proceed = page.locator('button:has-text("Proceed to Stage 4")');
    await expect(stage3Proceed).toBeVisible({ timeout: 10000 });

    page.once('dialog', dialog => {
      console.log('Dialog message:', dialog.message());
      dialog.accept();
    });
    await stage3Proceed.click();
    console.log('✓ Clicked Proceed to Stage 4');

    // Wait for stage 4 to start
    await expect(page.locator('text=4단계').or(page.locator('text=Stage 4'))).toBeVisible({ timeout: 30000 });
    console.log('✓ Stage 4 started');

    // Wait for stage 4 to complete (final stage)
    console.log('Waiting for Stage 4 to complete (final polish)...');
    const completionMessage = page.locator('text=Book Creation Complete').or(page.locator('text=완료'));
    await expect(completionMessage).toBeVisible({ timeout: 600000 }); // 10 minutes
    console.log('✓ Stage 4 completed - Book creation finished!');

    // Take final screenshot
    await page.screenshot({ path: 'bob-workflow-complete.png', fullPage: true });
    console.log('✓ Final screenshot saved to bob-workflow-complete.png');
  });

  test('Debug: Check current project state', async ({ page }) => {
    // Login
    await page.fill('input[type="text"]', 'bob');
    await page.fill('input[type="password"]', 'q1');
    await page.click('button:has-text("Login")');
    await expect(page.locator('text=👤 bob')).toBeVisible({ timeout: 10000 });

    // Get the first project
    await page.waitForSelector('.project-card', { timeout: 10000 });
    const projectCard = page.locator('.project-card').first();

    // Get project name
    const projectName = await projectCard.locator('h3').textContent();
    console.log('Project name:', projectName);

    // Check status badge
    const statusBadge = await projectCard.locator('[class*="status-badge"]').textContent();
    console.log('Status:', statusBadge);

    // Open project
    await projectCard.locator('button:has-text("View")').click();

    // Wait a bit for page to load
    await page.waitForTimeout(2000);

    // Take screenshot
    await page.screenshot({ path: 'bob-current-state.png', fullPage: true });
    console.log('Screenshot saved to bob-current-state.png');

    // Check what text appears on the page
    const bodyText = await page.locator('body').textContent();

    console.log('\n=== PAGE ANALYSIS ===');
    console.log('Has "1단계":', bodyText?.includes('1단계'));
    console.log('Has "2단계":', bodyText?.includes('2단계'));
    console.log('Has "3단계":', bodyText?.includes('3단계'));
    console.log('Has "4단계":', bodyText?.includes('4단계'));
    console.log('Has "Proceed":', bodyText?.includes('Proceed'));
    console.log('Has "계획 생성하기":', bodyText?.includes('계획 생성하기'));
    console.log('Has "Generated":', bodyText?.includes('Generated'));
    console.log('Has "Not generated":', bodyText?.includes('Not generated'));

    // Check for specific sections
    const sections = await page.locator('h3').allTextContents();
    console.log('\nPage sections:', sections);

    // Check for buttons
    const buttons = await page.locator('button').allTextContents();
    console.log('\nAvailable buttons:', buttons);
  });
});
