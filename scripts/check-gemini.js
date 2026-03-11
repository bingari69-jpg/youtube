const { GoogleGenerativeAI } = require('@google/generative-ai');

async function checkModels() {
  const key = 'AIzaSyCXmWAQFGCyTwqf3j8flldOSZkEpU8X96A';
  console.log('Using Key:', key ? 'FOUND' : 'NOT FOUND');

  const genAI = new GoogleGenerativeAI(key);
  const models = ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-1.0-pro'];
  for (const modelName of models) {
    try {
      const model = genAI.getGenerativeModel({ model: modelName });
      const result = await model.generateContent('Hello');
      console.log(`Model ${modelName}: SUCCESS`);
    } catch (e) {
      console.log(`Model ${modelName}: FAILED - ${e.message}`);
    }
  }
}

checkModels();
