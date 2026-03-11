const https = require('https');

const key = 'AIzaSyCXmWAQFGCyTwqf3j8flldOSZkEpU8X96A';
const url = `https://generativelanguage.googleapis.com/v1beta/models?key=${key}`;

https.get(url, (res) => {
  let data = '';
  res.on('data', (chunk) => { data += chunk; });
  res.on('end', () => {
    try {
      const json = JSON.parse(data);
      console.log('Available models:');
      json.models.forEach(m => {
        console.log(`- ${m.name}`);
      });
    } catch (e) {
      console.error('Error parsing response:', e.message);
      console.log('Raw output:', data);
    }
  });
}).on('error', (err) => {
  console.error('Error:', err.message);
});
