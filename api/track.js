/**
 * Tracking API — records page views from lead preview sites.
 *
 * Called via tracking pixel/script on each preview page.
 * Logs to Monday.com (updates visit count + opened status).
 *
 * Query params: ?phone=972XXXXXXXXX&name=BusinessName&t=timestamp
 */

const MONDAY_API_TOKEN = process.env.MONDAY_API_TOKEN || '';
const MONDAY_BOARD_ID = '5093635431';

// Column IDs
const COL_OPENED = 'color_mm1rpq5k';    // פתח אתר?
const COL_VISITS = 'numeric_mm1r9dgs';   // כניסות לאתר

// 1x1 transparent GIF
const PIXEL = Buffer.from('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7', 'base64');

export default async function handler(req, res) {
  // Return pixel immediately (don't block the browser)
  res.setHeader('Content-Type', 'image/gif');
  res.setHeader('Cache-Control', 'no-store, no-cache, must-revalidate');
  res.setHeader('Access-Control-Allow-Origin', '*');

  const { phone, name } = req.query;

  if (!phone) {
    return res.status(200).send(PIXEL);
  }

  // Fire and forget — update Monday.com in background
  if (MONDAY_API_TOKEN) {
    updateMonday(phone, name).catch(err => {
      console.error('Monday update error:', err.message);
    });
  }

  // Log for analytics
  console.log(`[TRACK] phone=${phone} name=${name || '?'} ip=${req.headers['x-forwarded-for'] || '?'} ua=${req.headers['user-agent']?.substring(0, 60) || '?'}`);

  return res.status(200).send(PIXEL);
}

async function updateMonday(phone, name) {
  // Find item by phone number
  const searchQuery = `
    query {
      boards(ids: [${MONDAY_BOARD_ID}]) {
        items_page(limit: 500) {
          items {
            id
            name
            column_values(ids: ["${COL_VISITS}"]) {
              id
              text
            }
          }
        }
      }
    }
  `;

  const searchResult = await mondayApi(searchQuery);
  const items = searchResult?.data?.boards?.[0]?.items_page?.items || [];

  // Find matching item by name (phone matching is harder with formatting)
  const decodedName = decodeURIComponent(name || '');
  const item = items.find(i =>
    i.name === decodedName ||
    i.name.includes(decodedName) ||
    decodedName.includes(i.name)
  );

  if (!item) {
    console.log(`[TRACK] No Monday item found for: ${decodedName}`);
    return;
  }

  // Get current visit count
  const currentVisits = parseInt(item.column_values?.[0]?.text || '0', 10);
  const newVisits = currentVisits + 1;

  // Update opened status + increment visit count
  const mutation = `
    mutation {
      change_multiple_column_values(
        board_id: ${MONDAY_BOARD_ID},
        item_id: ${item.id},
        column_values: "${JSON.stringify({
          [COL_OPENED]: { label: 'כן' },
          [COL_VISITS]: newVisits.toString(),
        }).replace(/"/g, '\\"')}"
      ) {
        id
      }
    }
  `;

  await mondayApi(mutation);
  console.log(`[TRACK] Updated ${decodedName}: visits=${newVisits}`);
}

async function mondayApi(query) {
  const res = await fetch('https://api.monday.com/v2', {
    method: 'POST',
    headers: {
      'Authorization': MONDAY_API_TOKEN,
      'Content-Type': 'application/json',
      'API-Version': '2024-10',
    },
    body: JSON.stringify({ query }),
  });
  return res.json();
}
