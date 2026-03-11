const https = require('https');

async function checkChannel() {
  const key = 'AIzaSyCXmWAQFGCyTwqf3j8flldOSZkEpU8X96A';
  const query = encodeURIComponent('침착맨');
  const url = `https://www.googleapis.com/youtube/v3/search?part=snippet&type=channel&q=${query}&key=${key}`;

  https.get(url, (res) => {
    let rawData = '';
    res.on('data', (chunk) => { rawData += chunk; });
    res.on('end', () => {
      try {
        const parsedData = JSON.parse(rawData);
        console.log('Search Data:', JSON.stringify(parsedData, null, 2));
      } catch (e) {
        console.error(e.message);
      }
    });
  }).on('error', (e) => {
    console.error(`Error: ${e.message}`);
  });
}

checkChannel();
