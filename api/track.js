/**
 * Tracking API — records page views from lead preview sites.
 * Logs to Monday.com (updates visit count + opened status).
 * Query params: ?phone=972XXXXXXXXX&name=BusinessName&t=timestamp
 */

const MONDAY_API_TOKEN = process.env.MONDAY_API_TOKEN || '';
const MONDAY_BOARD_ID = 5092777389;
const COL_PHONE = 'phone_mm16hqz2';
const COL_OPENED = 'color_mm1sg2gr';   // status: 0=Working, 1=Done, 2=Stuck
const COL_VISITS = 'numeric_mm1sdjj8';
const COL_TIME = 'numeric_mm1tw9yg';   // זמן באתר (שניות)

const PIXEL = Buffer.from('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7', 'base64');

export default async function handler(req, res) {
  res.setHeader('Content-Type', 'image/gif');
  res.setHeader('Cache-Control', 'no-store, no-cache, must-revalidate');
  res.setHeader('Access-Control-Allow-Origin', '*');

  const { phone, name, event, seconds } = req.query;
  if (!phone) return res.status(200).send(PIXEL);

  const isTimeEvent = event === 'time_on_site' && seconds;

  if (isTimeEvent) {
    console.log(`[TRACK] TIME phone=${phone} name=${name || '?'} seconds=${seconds}`);
  } else {
    console.log(`[TRACK] VIEW phone=${phone} name=${name || '?'}`);
  }

  if (MONDAY_API_TOKEN) {
    try {
      if (isTimeEvent) {
        await updateTimeOnSite(phone, parseInt(seconds, 10));
      } else {
        await updateMonday(phone, name);
      }
    } catch (err) {
      console.error(`[TRACK] ERROR: ${err.message}`);
    }
  } else {
    console.log('[TRACK] No MONDAY_API_TOKEN');
  }

  return res.status(200).send(PIXEL);
}

function normalizePhone(p) {
  let d = (p || '').replace(/\D/g, '');
  if (d.startsWith('972')) d = '0' + d.slice(3);
  if (!d.startsWith('0') && d.length === 9) d = '0' + d;
  return d;
}

async function updateMonday(phone, name) {
  const phoneLocal = normalizePhone(phone);
  if (!phoneLocal || phoneLocal.length < 9) {
    console.log(`[TRACK] Invalid phone: ${phone}`);
    return;
  }

  // Fetch items with phone + visits columns (paginated, 100 at a time)
  let items = [];
  let cursor = null;

  // First page
  const firstQuery = `query {
    boards(ids: [${MONDAY_BOARD_ID}]) {
      items_page(limit: 100) {
        cursor
        items {
          id name
          column_values(ids: ["${COL_PHONE}", "${COL_VISITS}"]) { id text }
        }
      }
    }
  }`;

  const firstResult = await mondayApi(firstQuery);
  if (firstResult?.errors) {
    console.error(`[TRACK] Query error: ${JSON.stringify(firstResult.errors).slice(0, 200)}`);
    return;
  }

  const page1 = firstResult?.data?.boards?.[0]?.items_page || {};
  items = page1.items || [];
  cursor = page1.cursor;

  // Find in first page
  let item = findByPhone(items, phoneLocal);

  // Paginate if not found
  while (!item && cursor) {
    const nextQuery = `query { next_items_page(cursor: "${cursor}", limit: 100) { cursor items { id name column_values(ids: ["${COL_PHONE}", "${COL_VISITS}"]) { id text } } } }`;
    const nextResult = await mondayApi(nextQuery);
    if (nextResult?.errors) break;
    const page = nextResult?.data?.next_items_page || {};
    item = findByPhone(page.items || [], phoneLocal);
    cursor = page.cursor;
  }

  if (!item) {
    console.log(`[TRACK] No item for phone=${phoneLocal}`);
    return;
  }

  const visitCol = item.column_values?.find(c => c.id === COL_VISITS);
  const currentVisits = parseInt(visitCol?.text || '0', 10);
  const newVisits = currentVisits + 1;

  // Status label "Done" (index 1) for "פתח אתר"
  const colValues = JSON.stringify({
    [COL_OPENED]: { index: 1 },
    [COL_VISITS]: newVisits.toString(),
  });

  const mutation = `mutation {
    change_multiple_column_values(
      board_id: ${MONDAY_BOARD_ID},
      item_id: ${item.id},
      column_values: ${JSON.stringify(colValues)}
    ) { id }
  }`;

  const mutResult = await mondayApi(mutation);
  if (mutResult?.errors) {
    console.error(`[TRACK] Mutation error: ${JSON.stringify(mutResult.errors).slice(0, 200)}`);
  } else {
    console.log(`[TRACK] OK: ${item.name} visits=${newVisits}`);
  }
}

async function updateTimeOnSite(phone, seconds) {
  const phoneLocal = normalizePhone(phone);
  if (!phoneLocal || phoneLocal.length < 9 || !seconds || seconds < 1) return;

  let cursor = null;
  let item = null;

  const firstQuery = `query {
    boards(ids: [${MONDAY_BOARD_ID}]) {
      items_page(limit: 100) {
        cursor
        items {
          id name
          column_values(ids: ["${COL_PHONE}", "${COL_TIME}"]) { id text }
        }
      }
    }
  }`;

  const firstResult = await mondayApi(firstQuery);
  if (firstResult?.errors) return;

  const page1 = firstResult?.data?.boards?.[0]?.items_page || {};
  item = findByPhone(page1.items || [], phoneLocal);
  cursor = page1.cursor;

  while (!item && cursor) {
    const nextQuery = `query { next_items_page(cursor: "${cursor}", limit: 100) { cursor items { id name column_values(ids: ["${COL_PHONE}", "${COL_TIME}"]) { id text } } } }`;
    const nextResult = await mondayApi(nextQuery);
    if (nextResult?.errors) break;
    const page = nextResult?.data?.next_items_page || {};
    item = findByPhone(page.items || [], phoneLocal);
    cursor = page.cursor;
  }

  if (!item) return;

  // Keep the maximum time (don't overwrite with lower value)
  const timeCol = item.column_values?.find(c => c.id === COL_TIME);
  const currentTime = parseInt(timeCol?.text || '0', 10);
  if (seconds <= currentTime) return;

  const colValues = JSON.stringify({ [COL_TIME]: seconds.toString() });
  const mutation = `mutation {
    change_multiple_column_values(
      board_id: ${MONDAY_BOARD_ID},
      item_id: ${item.id},
      column_values: ${JSON.stringify(colValues)}
    ) { id }
  }`;

  const result = await mondayApi(mutation);
  if (result?.errors) {
    console.error(`[TRACK] Time mutation error: ${JSON.stringify(result.errors).slice(0, 200)}`);
  } else {
    console.log(`[TRACK] TIME OK: ${item.name} ${currentTime}s → ${seconds}s`);
  }
}

function findByPhone(items, phoneLocal) {
  return items.find(i => {
    const pCol = i.column_values?.find(c => c.id === COL_PHONE);
    const itemPhone = normalizePhone(pCol?.text || '');
    return itemPhone === phoneLocal;
  });
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
