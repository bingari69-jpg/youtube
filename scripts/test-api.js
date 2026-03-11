const { GoogleGenerativeAI } = require('@google/generative-ai');
const fs = require('fs');
const path = require('path');

async function testApi() {
  let key = '';
  try {
    const env = fs.readFileSync(path.join(process.cwd(), '.env.local'), 'utf8');
    const match = env.match(/YOUTUBE_API_KEY=(.*)/);
    if (match) key = match[1].trim();
  } catch (e) {}

  if (!key) {
    console.log('Key not found in .env.local');
    return;
  }

  console.log('Testing with Key:', key.slice(0, 5) + '...');
  const genAI = new GoogleGenerativeAI(key);

  const testModels = ['gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-pro-latest', 'gemini-flash-latest'];
  for (const m of testModels) {
    try {
      console.log(`Trying ${m}...`);
      const model = genAI.getGenerativeModel({ model: m });
      const res = await model.generateContent('Hi');
      console.log(`Model ${m}: SUCCESS`);
      console.log('Short Response:', (await res.response.text()).slice(0, 30));
      return; // Exit on first success
    } catch (e) {
      console.log(`Model ${m}: FAILED - ${e.message}`);
    }
  }
}

testApi();
