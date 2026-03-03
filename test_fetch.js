const fetch = require('node-fetch');

async function run() {
  const resp = await fetch('https://media-seven-eta.vercel.app/api/casting', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ test: "data" })
  });
  console.log(resp.status);
  console.log(await resp.text());
}
run();
