const puppeteer = require('puppeteer');
const path = require('path');
const { execSync } = require('child_process');

(async () => {
  const timestamp = Date.now();
  const testEmail = `reg_test_${timestamp}@inkraft.test`;
  const testPass = 'TestPass123!';
  
  console.log(`Test email: ${testEmail}`);
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
  
  // Auto-accept confirmation/alert dialogs
  page.on('dialog', async dialog => {
    console.log('Dialog intercepted:', dialog.message());
    await dialog.accept();
  });

  try {
    // 1. Navigate to Register page
    console.log('Navigating to register page...');
    await page.goto('http://127.0.0.1:8000/register.html', { waitUntil: 'networkidle2' });

    console.log('Entering registration details...');
    await page.waitForSelector('#email-input');
    await page.type('#email-input', testEmail);
    await page.type('#password-input', testPass);
    await page.type('#password-confirm-input', testPass);
    await page.click('button[type="submit"]');

    console.log('Waiting for route change after registration...');
    await page.waitForFunction(() => window.location.href.includes('/dashboard.html') || window.location.href.includes('/index.html'), { timeout: 15000 });
    console.log('Registered and logged in successfully.');

    // Save auth screenshots
    await page.goto('http://127.0.0.1:8000/login.html', { waitUntil: 'networkidle2' });
    await page.screenshot({ path: 'C:\\Users\\dell\\.gemini\\antigravity\\brain\\9a7ec11a-f0f4-43da-baca-fb7c86f6b5f6\\auth_login.png' });
    console.log('Saved auth_login.png');

    await page.goto('http://127.0.0.1:8000/register.html', { waitUntil: 'networkidle2' });
    await page.screenshot({ path: 'C:\\Users\\dell\\.gemini\\antigravity\\brain\\9a7ec11a-f0f4-43da-baca-fb7c86f6b5f6\\auth_register.png' });
    console.log('Saved auth_register.png');

    // Go back to main app to get token / user ID
    await page.goto('http://127.0.0.1:8000/index.html', { waitUntil: 'networkidle2' });
    await page.screenshot({ path: 'C:\\Users\\dell\\.gemini\\antigravity\\brain\\9a7ec11a-f0f4-43da-baca-fb7c86f6b5f6\\main_wizard.png' });
    console.log('Saved main_wizard.png');

    // Extract user ID from localStorage
    const userDataStr = await page.evaluate(() => localStorage.getItem('ntc_user'));
    if (!userDataStr) {
      throw new Error('User data not found in localStorage after login.');
    }
    const userData = JSON.parse(userDataStr);
    const userId = userData.id;
    console.log(`Logged in User ID: ${userId}`);

    // 2. Set up mock comic in DB and files
    console.log('Executing create_mock_comic.py...');
    const pythonCmd = `python C:\\Users\\dell\\AppData\\Local\\Temp\\create_mock_comic.py ${userId}`;
    console.log(`Running: ${pythonCmd}`);
    const mockOutput = execSync(pythonCmd).toString();
    console.log('Mock setup output:', mockOutput);

    // 3. Test Character Vault & Deletions
    console.log('Navigating to Character Vault (/characters.html)...');
    await page.goto('http://127.0.0.1:8000/characters.html', { waitUntil: 'networkidle2' });
    await new Promise(r => setTimeout(r, 1000));
    await page.screenshot({ path: 'C:\\Users\\dell\\.gemini\\antigravity\\brain\\9a7ec11a-f0f4-43da-baca-fb7c86f6b5f6\\vault_empty.png' });
    console.log('Saved vault_empty.png');

    // Add new character
    console.log('Adding a test character to the vault...');
    await page.click('#create-char-btn');
    await page.waitForSelector('#char-name');
    await page.type('#char-name', 'TestDeleteMe');
    await page.type('#char-features', 'A test character created for regression verification.');
    
    // Choose gender
    await page.select('#char-gender', 'female');
    
    // Save
    await page.click('#save-char-btn');
    console.log('Waiting for character list to refresh...');
    await new Promise(r => setTimeout(r, 1500));
    await page.screenshot({ path: 'C:\\Users\\dell\\.gemini\\antigravity\\brain\\9a7ec11a-f0f4-43da-baca-fb7c86f6b5f6\\vault_with_character.png' });
    console.log('Saved vault_with_character.png');

    // Delete character
    console.log('Deleting the test character...');
    // Find the delete button for TestDeleteMe
    const deleteBtnSelector = '.card-action-btn.btn-delete';
    await page.waitForSelector(deleteBtnSelector);
    await page.click(deleteBtnSelector);
    
    // Wait for the delete modal and confirm
    await page.waitForSelector('#delete-confirm-btn');
    await new Promise(r => setTimeout(r, 500));
    await page.screenshot({ path: 'C:\\Users\\dell\\.gemini\\antigravity\\brain\\9a7ec11a-f0f4-43da-baca-fb7c86f6b5f6\\vault_delete_modal.png' });
    console.log('Saved vault_delete_modal.png');
    await page.click('#delete-confirm-btn');
    
    // Wait for deletion request to finish and reload
    await new Promise(r => setTimeout(r, 1500));
    await page.screenshot({ path: 'C:\\Users\\dell\\.gemini\\antigravity\\brain\\9a7ec11a-f0f4-43da-baca-fb7c86f6b5f6\\vault_after_delete.png' });
    console.log('Saved vault_after_delete.png');

    // 4. Test History & PDF download
    console.log('Navigating to History page (/history.html)...');
    await page.goto('http://127.0.0.1:8000/history.html', { waitUntil: 'networkidle2' });
    await new Promise(r => setTimeout(r, 1000));
    await page.screenshot({ path: 'C:\\Users\\dell\\.gemini\\antigravity\\brain\\9a7ec11a-f0f4-43da-baca-fb7c86f6b5f6\\history_list.png' });
    console.log('Saved history_list.png');

    // Click on the mock comic card
    console.log('Opening comic viewer modal...');
    const comicCardSelector = '.hist-card';
    await page.waitForSelector(comicCardSelector);
    await page.click(comicCardSelector);
    await new Promise(r => setTimeout(r, 1000));
    
    // Intercept download call
    console.log('Setting up PDF download request listener...');
    let downloadStatus = null;
    let downloadHeaders = null;
    
    page.on('response', response => {
      if (response.url().includes('/pdf')) {
        downloadStatus = response.status();
        downloadHeaders = response.headers();
        console.log(`[Intercepted PDF Download] Status: ${downloadStatus}, Content-Type: ${downloadHeaders['content-type']}`);
      }
    });

    await page.screenshot({ path: 'C:\\Users\\dell\\.gemini\\antigravity\\brain\\9a7ec11a-f0f4-43da-baca-fb7c86f6b5f6\\history_viewer_modal.png' });
    console.log('Saved history_viewer_modal.png');

    console.log('Clicking Download PDF button...');
    await page.waitForSelector('#modal-download-pdf');
    await page.click('#modal-download-pdf');

    // Wait for the download response to come back (or 5 seconds timeout)
    const downloadStartTime = Date.now();
    while (downloadStatus === null && Date.now() - downloadStartTime < 8000) {
      await new Promise(r => setTimeout(r, 500));
    }

    if (downloadStatus === 200) {
      console.log('SUCCESS: PDF Download works! Returned 200 OK (no 401).');
    } else {
      throw new Error(`PDF Download failed or returned status: ${downloadStatus}`);
    }

  } catch (err) {
    console.error('Regression run failed:', err.message);
    await page.screenshot({ path: 'C:\\Users\\dell\\.gemini\\antigravity\\brain\\9a7ec11a-f0f4-43da-baca-fb7c86f6b5f6\\regression_error.png' });
    await browser.close();
    process.exit(1);
  }

  await browser.close();
  console.log('Regression run complete successfully.');
})();
