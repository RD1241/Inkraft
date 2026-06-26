const puppeteer = require('puppeteer');
const path = require('path');

(async () => {
  console.log('Launching browser...');
  const browser = await puppeteer.launch({
    headless: "new",
    defaultViewport: { width: 1280, height: 800 }
  });
  const page = await browser.newPage();

  // Pipe page console logs to terminal
  page.on('console', msg => console.log('PAGE LOG:', msg.text()));
  page.on('pageerror', err => console.log('PAGE ERROR:', err.toString()));
  
  // Log request failures
  page.on('requestfailed', request => {
    const failure = request.failure();
    console.log('REQUEST FAILED:', request.url(), failure ? failure.errorText : 'unknown');
  });
  
  // Log response status >= 400
  page.on('response', response => {
    if (response.status() >= 400) {
      console.log('RESPONSE ERROR:', response.url(), response.status());
    }
  });

  try {
    console.log('Navigating to login page...');
    await page.goto('http://127.0.0.1:8000/login.html', { waitUntil: 'networkidle2' });

    console.log('Logging in...');
    await page.waitForSelector('#email-input');
    await page.type('#email-input', 'kaitomei_test@inkraft.ai');
    await page.type('#password-input', 'TestPass123!');
    await page.click('button[type="submit"]');

    // Wait briefly to see if route changes
    try {
      await page.waitForFunction(() => window.location.href.includes('/dashboard.html') || window.location.href.includes('/index.html'), { timeout: 5000 });
      console.log('Successfully logged in!');
    } catch (e) {
      console.log('Login failed or timed out. Attempting registration...');
      await page.goto('http://127.0.0.1:8000/register.html', { waitUntil: 'networkidle2' });
      await page.waitForSelector('#email-input');
      await page.type('#email-input', 'kaitomei_test@inkraft.ai');
      await page.type('#password-input', 'TestPass123!');
      await page.type('#password-confirm-input', 'TestPass123!');
      await page.click('button[type="submit"]');
      
      console.log('Waiting for route change after registration...');
      await page.waitForFunction(() => window.location.href.includes('/dashboard.html') || window.location.href.includes('/index.html'), { timeout: 15000 });
      console.log('Registered and logged in!');
    }
  } catch (err) {
    console.error('Authentication phase failed:', err.message);
    const errPath = 'C:\\Users\\dell\\.gemini\\antigravity\\brain\\9a7ec11a-f0f4-43da-baca-fb7c86f6b5f6\\login_error.png';
    await page.screenshot({ path: errPath });
    console.log('Saved error screenshot to:', errPath);
    await browser.close();
    process.exit(1);
  }

  console.log('Navigating to generate page...');
  await page.goto('http://127.0.0.1:8000/index.html', { waitUntil: 'networkidle2' });

  console.log('Entering story...');
  await page.waitForSelector('#novel-input');
  
  // Clear default text and type the story
  await page.focus('#novel-input');
  await page.keyboard.down('Control');
  await page.keyboard.press('A');
  await page.keyboard.up('Control');
  await page.keyboard.press('Backspace');
  await page.type('#novel-input', "Kaito sat alone in the school library, the only sound the soft hum of the ceiling lights. He stared at the letter in his hands, reading it for the third time. Across the room, the door creaked open and Mei stepped in, her bag slung over one shoulder. She froze when she saw his expression. 'What happened?' she asked, walking closer. Kaito didn't look up. 'They're closing the dojo. After twenty years, it's just... over.' He crumpled the letter and pressed it against his chest. Mei sat down beside him, saying nothing, just staying close as the silence settled between them.");

  console.log('Navigating to Step 2...');
  await page.click('#next-step-btn');
  await new Promise(r => setTimeout(r, 500));

  console.log('Selecting Manga style...');
  await page.waitForSelector('.style-pill[data-value="manga"]');
  await page.click('.style-pill[data-value="manga"]');

  console.log('Navigating to Step 3...');
  await page.click('#next-step-btn');
  await new Promise(r => setTimeout(r, 500));

  console.log('Selecting Panel Strip format...');
  await page.waitForSelector('.format-card[data-value="panel_strip"]');
  await page.click('.format-card[data-value="panel_strip"]');

  console.log('Navigating to Step 4...');
  await page.click('#next-step-btn');
  await new Promise(r => setTimeout(r, 500));

  console.log('Navigating to Step 5...');
  await page.click('#next-step-btn');
  await new Promise(r => setTimeout(r, 500));

  console.log('Clicking Paint Comic Page!...');
  await page.waitForSelector('#generate-btn');
  await page.click('#generate-btn');

  // Wait for the status text to include "Planning storyboard layout"
  console.log('Waiting for Storyboard stage to fire...');
  let storyboardStageFired = false;
  const startTime = Date.now();
  
  while (Date.now() - startTime < 180000) { // 3 minute timeout
    const progressText = await page.evaluate(() => {
      const el = document.getElementById('raw-progress-subtitle') || document.getElementById('loading-text');
      return el ? el.textContent : '';
    });
    console.log(`  [Progress] ${progressText}`);
    
    if (progressText.toLowerCase().includes('planning storyboard') || progressText.toLowerCase().includes('storyboard')) {
      storyboardStageFired = true;
      break;
    }
    
    if (progressText.toLowerCase().includes('failed') || progressText.toLowerCase().includes('error')) {
      console.log('Pipeline failed.');
      break;
    }
    
    if (progressText.toLowerCase().includes('drawing panel') || progressText.toLowerCase().includes('drawing')) {
      storyboardStageFired = true;
      console.log('Storyboard stage fired but already transitioned to drawing.');
      break;
    }
    
    await new Promise(r => setTimeout(r, 1000));
  }

  // Take the screenshot
  const screenshotPath = 'C:\\Users\\dell\\.gemini\\antigravity\\brain\\9a7ec11a-f0f4-43da-baca-fb7c86f6b5f6\\storyboard_progress.png';
  console.log('Taking screenshot...');
  await page.screenshot({ path: screenshotPath });
  console.log('Screenshot saved to:', screenshotPath);

  // Poll for completion to let it finish generation
  console.log('Waiting for comic generation to complete...');
  const genStartTime = Date.now();
  while (Date.now() - genStartTime < 600000) { // 10 minute timeout
    const isCompleted = await page.evaluate(() => {
      const resultsState = document.getElementById('results-state');
      return resultsState && !resultsState.classList.contains('hidden');
    });
    if (isCompleted) {
      console.log('Generation completed successfully!');
      break;
    }
    const isFailed = await page.evaluate(() => {
      const errBanner = document.getElementById('error-banner');
      return errBanner && !errBanner.classList.contains('hidden');
    });
    if (isFailed) {
      const errMsg = await page.evaluate(() => document.getElementById('error-text').textContent);
      console.log('Generation failed:', errMsg);
      break;
    }
    await new Promise(r => setTimeout(r, 5000));
  }

  await browser.close();
  console.log('Browser closed.');
})();
