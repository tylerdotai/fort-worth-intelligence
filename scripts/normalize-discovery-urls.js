#!/usr/bin/env node
const fs = require('fs');
const path = require('path');

const inputPath = path.join(__dirname, '..', 'data', 'raw', 'discovery_urls.txt');
const outputPath = path.join(__dirname, '..', 'data', 'raw', 'discovery_urls.normalized.json');

const lines = fs.readFileSync(inputPath, 'utf8')
  .split('\n')
  .map(s => s.trim())
  .filter(Boolean);

const normalized = lines.map((url, index) => {
  let host = '';
  try {
    host = new URL(url).hostname;
  } catch {}
  return {
    id: index + 1,
    url,
    host,
    discoveredFrom: 'fwtx-scraper',
    validationStatus: 'unvalidated',
    tier: null,
    accessType: [],
    notes: ''
  };
});

fs.writeFileSync(outputPath, JSON.stringify(normalized, null, 2));
console.log(`Wrote ${normalized.length} records to ${outputPath}`);
