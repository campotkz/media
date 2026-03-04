const fs = require('fs');
const S_URL = "https://waekzofajzqcpoeldhkt.supabase.co";
const S_KEY = "sb_publishable_XVByRUkaKbM-11ChwOd2Aw_y24CSb4V";

async function checkData() {
    const url = `${S_URL}/rest/v1/casting_applications?select=*`;
    const res = await fetch(url, {
        headers: {
            'apikey': S_KEY,
            'Authorization': `Bearer ${S_KEY}`
        }
    });
    const data = await res.json();
    fs.writeFileSync('test_data.json', JSON.stringify(data, null, 2));
    console.log("Data saved to test_data.json");
}
checkData();
