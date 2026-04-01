#!/usr/bin/env python3
"""Simple web server for browsing eval result diffs. No dependencies beyond stdlib.

Usage: python evals/server.py [--port 8089]
"""

import json
import sys
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

RESULTS_DIR = Path(__file__).resolve().parent / "results"
PORT = 8089

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Eval Results Browser</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<style>
  .response-text { font-size: 0.8125rem; line-height: 1.6; }
  .response-text h1 { font-size: 1.25rem; font-weight: 700; margin: 1rem 0 0.5rem; color: #e5e7eb; }
  .response-text h2 { font-size: 1.1rem; font-weight: 700; margin: 1rem 0 0.5rem; color: #e5e7eb; }
  .response-text h3 { font-size: 0.95rem; font-weight: 600; margin: 0.75rem 0 0.25rem; color: #d1d5db; }
  .response-text p { margin: 0.5rem 0; }
  .response-text ul, .response-text ol { margin: 0.5rem 0; padding-left: 1.5rem; }
  .response-text ul { list-style: disc; }
  .response-text ol { list-style: decimal; }
  .response-text li { margin: 0.2rem 0; }
  .response-text code { background: rgba(255,255,255,0.06); padding: 0.1rem 0.35rem; border-radius: 3px; font-size: 0.8rem; }
  .response-text pre { background: rgba(0,0,0,0.4); border: 1px solid rgba(255,255,255,0.08); border-radius: 6px; padding: 0.75rem; margin: 0.5rem 0; overflow-x: auto; }
  .response-text pre code { background: none; padding: 0; font-size: 0.78rem; }
  .response-text hr { border-color: rgba(255,255,255,0.1); margin: 1rem 0; }
  .response-text strong { color: #e5e7eb; }
  .response-text a { color: #60a5fa; text-decoration: underline; }
  .row-fixed { border-left: 3px solid #22c55e; }
  .row-regressed { border-left: 3px solid #ef4444; }
  .row-both-fail { border-left: 3px solid #eab308; }
  .row-both-pass { border-left: 3px solid transparent; }
</style>
</head>
<body class="bg-gray-950 text-gray-200 min-h-screen">

<div id="app" class="max-w-7xl mx-auto px-4 py-6">
  <!-- Header -->
  <div class="flex items-center justify-between mb-6">
    <h1 class="text-lg font-semibold text-gray-100">Eval Results Browser</h1>
    <div class="text-xs text-gray-500">Comparing two eval runs</div>
  </div>

  <!-- File pickers -->
  <div class="grid grid-cols-2 gap-4 mb-6">
    <div>
      <label class="block text-xs text-gray-400 mb-1 font-medium">A (older) <span id="badge-a"></span></label>
      <select id="sel-a" class="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500">
        <option value="">Loading...</option>
      </select>
    </div>
    <div>
      <label class="block text-xs text-gray-400 mb-1 font-medium">B (newer) <span id="badge-b"></span></label>
      <select id="sel-b" class="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500">
        <option value="">Loading...</option>
      </select>
    </div>
  </div>

  <!-- Summary bar -->
  <div id="summary" class="hidden mb-6 bg-gray-900 border border-gray-800 rounded-lg p-4">
    <div class="grid grid-cols-4 gap-4 text-center">
      <div>
        <div class="text-xs text-gray-500 mb-1">A pass rate</div>
        <div id="sum-a-rate" class="text-xl font-bold">—</div>
      </div>
      <div>
        <div class="text-xs text-gray-500 mb-1">B pass rate</div>
        <div id="sum-b-rate" class="text-xl font-bold">—</div>
      </div>
      <div>
        <div class="text-xs text-gray-500 mb-1">Delta</div>
        <div id="sum-delta" class="text-xl font-bold">—</div>
      </div>
      <div>
        <div class="text-xs text-gray-500 mb-1">Changes</div>
        <div id="sum-changes" class="text-sm mt-1">—</div>
      </div>
    </div>
  </div>

  <!-- Filter tabs -->
  <div id="filters" class="hidden mb-4 flex gap-2">
    <button data-filter="all" class="filter-btn px-3 py-1 text-xs rounded-full bg-gray-800 text-gray-300 hover:bg-gray-700">All</button>
    <button data-filter="fixed" class="filter-btn px-3 py-1 text-xs rounded-full bg-gray-800 text-green-400 hover:bg-gray-700">Fixed</button>
    <button data-filter="regressed" class="filter-btn px-3 py-1 text-xs rounded-full bg-gray-800 text-red-400 hover:bg-gray-700">Regressed</button>
    <button data-filter="both-fail" class="filter-btn px-3 py-1 text-xs rounded-full bg-gray-800 text-yellow-400 hover:bg-gray-700">Both Fail</button>
    <button data-filter="both-pass" class="filter-btn px-3 py-1 text-xs rounded-full bg-gray-800 text-gray-400 hover:bg-gray-700">Both Pass</button>
  </div>

  <!-- Results table -->
  <div id="results" class="hidden">
    <table class="w-full text-sm">
      <thead>
        <tr class="text-xs text-gray-500 border-b border-gray-800">
          <th class="text-left py-2 px-2 w-8"></th>
          <th class="text-left py-2 px-2">ID</th>
          <th class="text-left py-2 px-2">Cluster</th>
          <th class="text-left py-2 px-2">Question</th>
          <th class="text-center py-2 px-2">A</th>
          <th class="text-center py-2 px-2">B</th>
          <th class="text-left py-2 px-2">Detail</th>
        </tr>
      </thead>
      <tbody id="results-body"></tbody>
    </table>
  </div>

  <!-- Empty state -->
  <div id="empty" class="text-center py-20 text-gray-600">
    <p class="text-lg mb-2">Select two result files to compare</p>
    <p class="text-sm">Choose files from the dropdowns above</p>
  </div>
</div>

<!-- Expanded response modal -->
<div id="modal" class="hidden fixed inset-0 bg-black/70 z-50 overflow-auto">
  <div class="max-w-7xl mx-auto p-6">
    <div class="bg-gray-900 border border-gray-700 rounded-lg overflow-hidden">
      <div class="flex items-center justify-between px-4 py-3 border-b border-gray-800">
        <div>
          <span id="modal-id" class="font-mono font-bold text-gray-100"></span>
          <span id="modal-question" class="ml-3 text-gray-400 text-sm"></span>
        </div>
        <button id="modal-close" class="text-gray-500 hover:text-gray-300 text-lg px-2">&times;</button>
      </div>
      <!-- Grading detail -->
      <div id="modal-grading" class="px-4 py-3 border-b border-gray-800 grid grid-cols-2 gap-4 text-xs"></div>
      <!-- Side by side responses -->
      <div class="grid grid-cols-2 divide-x divide-gray-800">
        <div>
          <div class="px-4 py-2 bg-gray-800/50 text-xs text-gray-400 font-medium">A — <span id="modal-a-file"></span></div>
          <div id="modal-a-response" class="response-text p-4 max-h-[70vh] overflow-auto text-gray-300"></div>
        </div>
        <div>
          <div class="px-4 py-2 bg-gray-800/50 text-xs text-gray-400 font-medium">B — <span id="modal-b-file"></span></div>
          <div id="modal-b-response" class="response-text p-4 max-h-[70vh] overflow-auto text-gray-300"></div>
        </div>
      </div>
    </div>
  </div>
</div>

<script>
const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

let dataA = null, dataB = null;
let currentFilter = 'all';

// --- Init ---
function updateBadge(side) {
  const sel = $(`#sel-${side}`);
  const badge = $(`#badge-${side}`);
  const val = sel.value || '';
  if (val.startsWith('baseline-')) {
    badge.textContent = 'BASELINE — NO SKILLS';
    badge.className = 'ml-2 text-xs font-bold text-orange-400 bg-orange-400/10 px-1.5 py-0.5 rounded';
  } else {
    badge.textContent = '';
    badge.className = '';
  }
}

async function init() {
  const res = await fetch('/api/results');
  const files = await res.json();

  const selA = $('#sel-a');
  const selB = $('#sel-b');
  selA.innerHTML = '<option value="">— select —</option>';
  selB.innerHTML = '<option value="">— select —</option>';

  for (const f of files) {
    const label = `${f.filename}  (${f.passed}/${f.total}, ${(f.pass_rate * 100).toFixed(1)}%)`;
    selA.innerHTML += `<option value="${f.filename}">${label}</option>`;
    selB.innerHTML += `<option value="${f.filename}">${label}</option>`;
  }

  // Auto-select two most recent quality files
  const qualityFiles = files.filter(f => f.filename.startsWith('quality-'));
  if (qualityFiles.length >= 2) {
    selA.value = qualityFiles[1].filename; // second newest
    selB.value = qualityFiles[0].filename; // newest
    await loadAndCompare();
  }

  selA.addEventListener('change', () => { updateBadge('a'); loadAndCompare(); });
  selB.addEventListener('change', () => { updateBadge('b'); loadAndCompare(); });
  updateBadge('a');
  updateBadge('b');

  // Filter buttons
  $$('.filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      currentFilter = btn.dataset.filter;
      $$('.filter-btn').forEach(b => b.classList.remove('ring-1', 'ring-gray-500'));
      btn.classList.add('ring-1', 'ring-gray-500');
      applyFilter();
    });
  });
  // Set initial active
  $('[data-filter="all"]').classList.add('ring-1', 'ring-gray-500');

  // Modal close
  $('#modal-close').addEventListener('click', () => $('#modal').classList.add('hidden'));
  $('#modal').addEventListener('click', (e) => {
    if (e.target === $('#modal')) $('#modal').classList.add('hidden');
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') $('#modal').classList.add('hidden');
  });
}

async function loadAndCompare() {
  const fileA = $('#sel-a').value;
  const fileB = $('#sel-b').value;
  if (!fileA || !fileB) {
    $('#summary').classList.add('hidden');
    $('#filters').classList.add('hidden');
    $('#results').classList.add('hidden');
    $('#empty').classList.remove('hidden');
    return;
  }

  const [resA, resB] = await Promise.all([
    fetch(`/api/results/${fileA}`).then(r => r.json()),
    fetch(`/api/results/${fileB}`).then(r => r.json()),
  ]);
  dataA = resA;
  dataB = resB;

  renderComparison();
}

function classify(ra, rb) {
  if (!ra) return rb?.passed ? 'only-b-pass' : 'only-b-fail';
  if (!rb) return ra?.passed ? 'only-a-pass' : 'only-a-fail';
  if (!ra.passed && rb.passed) return 'fixed';
  if (ra.passed && !rb.passed) return 'regressed';
  if (ra.passed && rb.passed) return 'both-pass';
  return 'both-fail';
}

function renderComparison() {
  const aById = Object.fromEntries(dataA.results.map(r => [r.id, r]));
  const bById = Object.fromEntries(dataB.results.map(r => [r.id, r]));
  const allIds = [...new Set([...dataA.results.map(r => r.id), ...dataB.results.map(r => r.id)])];

  let counts = { fixed: 0, regressed: 0, 'both-pass': 0, 'both-fail': 0 };
  const rows = allIds.map(id => {
    const ra = aById[id], rb = bById[id];
    const status = classify(ra, rb);
    if (counts[status] !== undefined) counts[status]++;
    return { id, ra, rb, status };
  });

  // Sort: regressed first, then fixed, then both-fail, then both-pass
  const order = { regressed: 0, fixed: 1, 'both-fail': 2, 'both-pass': 3 };
  rows.sort((a, b) => (order[a.status] ?? 9) - (order[b.status] ?? 9));

  // Summary
  const aRate = (dataA.pass_rate * 100);
  const bRate = (dataB.pass_rate * 100);
  const delta = bRate - aRate;

  $('#sum-a-rate').textContent = `${aRate.toFixed(1)}%`;
  $('#sum-a-rate').className = 'text-xl font-bold ' + (aRate >= 80 ? 'text-green-400' : aRate >= 50 ? 'text-yellow-400' : 'text-red-400');

  $('#sum-b-rate').textContent = `${bRate.toFixed(1)}%`;
  $('#sum-b-rate').className = 'text-xl font-bold ' + (bRate >= 80 ? 'text-green-400' : bRate >= 50 ? 'text-yellow-400' : 'text-red-400');

  const sign = delta >= 0 ? '+' : '';
  $('#sum-delta').textContent = `${sign}${delta.toFixed(1)}%`;
  $('#sum-delta').className = 'text-xl font-bold ' + (delta > 0 ? 'text-green-400' : delta < 0 ? 'text-red-400' : 'text-gray-500');

  $('#sum-changes').innerHTML = `
    <span class="text-green-400">${counts.fixed} fixed</span> ·
    <span class="text-red-400">${counts.regressed} regressed</span> ·
    <span class="text-yellow-400">${counts['both-fail']} both fail</span>
  `;

  // Update filter button counts
  $('[data-filter="all"]').textContent = `All (${allIds.length})`;
  $('[data-filter="fixed"]').textContent = `Fixed (${counts.fixed})`;
  $('[data-filter="regressed"]').textContent = `Regressed (${counts.regressed})`;
  $('[data-filter="both-fail"]').textContent = `Both Fail (${counts['both-fail']})`;
  $('[data-filter="both-pass"]').textContent = `Both Pass (${counts['both-pass']})`;

  // Render rows
  const tbody = $('#results-body');
  tbody.innerHTML = '';
  for (const row of rows) {
    const tr = document.createElement('tr');
    tr.className = `border-b border-gray-800/50 hover:bg-gray-900/50 cursor-pointer row-${row.status}`;
    tr.dataset.status = row.status;
    tr.dataset.id = row.id;

    const statusIcon = {
      fixed: '<span class="text-green-400">↑</span>',
      regressed: '<span class="text-red-400">↓</span>',
      'both-pass': '<span class="text-gray-600">✓</span>',
      'both-fail': '<span class="text-yellow-400">✗</span>',
    }[row.status] || '';

    const passCell = (r) => {
      if (!r) return '<span class="text-gray-700">—</span>';
      return r.passed
        ? '<span class="text-green-400">PASS</span>'
        : '<span class="text-red-400">FAIL</span>';
    };

    const detail = [];
    const r = row.rb || row.ra;
    if (r && !r.passed) {
      const missed = r.contains_missed || [];
      const violated = r.not_contains_violated || [];
      if (missed.length) detail.push(`missing: ${missed.join(', ')}`);
      if (violated.length) detail.push(`violated: ${violated.join(', ')}`);
    }

    const question = (row.ra || row.rb)?.question || '';
    const qShort = question.length > 55 ? question.slice(0, 55) + '…' : question;

    tr.innerHTML = `
      <td class="py-2 px-2 text-center">${statusIcon}</td>
      <td class="py-2 px-2 font-mono text-xs text-gray-300 whitespace-nowrap">${row.id}</td>
      <td class="py-2 px-2 text-xs text-gray-500">${(row.ra || row.rb)?.cluster || ''}</td>
      <td class="py-2 px-2 text-xs text-gray-400 truncate max-w-xs" title="${question.replace(/"/g, '&quot;')}">${qShort}</td>
      <td class="py-2 px-2 text-center text-xs">${passCell(row.ra)}</td>
      <td class="py-2 px-2 text-center text-xs">${passCell(row.rb)}</td>
      <td class="py-2 px-2 text-xs text-gray-500 truncate max-w-xs">${detail.join('; ')}</td>
    `;

    tr.addEventListener('click', () => openModal(row));
    tbody.appendChild(tr);
  }

  $('#summary').classList.remove('hidden');
  $('#filters').classList.remove('hidden');
  $('#results').classList.remove('hidden');
  $('#empty').classList.add('hidden');
  applyFilter();
}

function applyFilter() {
  $$('#results-body tr').forEach(tr => {
    if (currentFilter === 'all' || tr.dataset.status === currentFilter) {
      tr.classList.remove('hidden');
    } else {
      tr.classList.add('hidden');
    }
  });
}

function formatGrading(r, label) {
  if (!r) return `<div class="text-gray-600">${label}: not present</div>`;
  const matched = r.contains_matched || [];
  const missed = r.contains_missed || [];
  const violated = r.not_contains_violated || [];
  const total = r.total_expected || 0;
  const passClass = r.passed ? 'text-green-400' : 'text-red-400';

  let html = `<div>
    <div class="font-medium text-gray-300 mb-1">${label} — <span class="${passClass}">${r.passed ? 'PASS' : 'FAIL'}</span> <span class="text-gray-500">[${matched.length}/${total}]</span></div>`;

  if (matched.length) {
    html += `<div class="text-green-400/70">✓ ${matched.join(', ')}</div>`;
  }
  if (missed.length) {
    html += `<div class="text-red-400/70">✗ missing: ${missed.join(', ')}</div>`;
  }
  if (violated.length) {
    html += `<div class="text-red-400/70">⚠ violated: ${violated.join(', ')}</div>`;
  }
  html += `<div class="text-gray-600 mt-1">${(r.response_length || 0).toLocaleString()} chars</div>`;
  html += '</div>';
  return html;
}

function openModal(row) {
  $('#modal-id').textContent = row.id;
  $('#modal-question').textContent = (row.ra || row.rb)?.question || '';
  $('#modal-a-file').textContent = $('#sel-a').value;
  $('#modal-b-file').textContent = $('#sel-b').value;

  $('#modal-grading').innerHTML = formatGrading(row.ra, 'A') + formatGrading(row.rb, 'B');

  $('#modal-a-response').innerHTML = marked.parse(row.ra?.response || '*(not present in A)*');
  $('#modal-b-response').innerHTML = marked.parse(row.rb?.response || '*(not present in B)*');

  $('#modal').classList.remove('hidden');
}

init();
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/":
            self._send(200, "text/html", HTML_PAGE)
        elif path == "/api/results":
            self._send_json(200, self._list_results())
        elif path.startswith("/api/results/"):
            filename = path[len("/api/results/"):]
            self._serve_result_file(filename)
        else:
            self._send(404, "text/plain", "Not found")

    def _list_results(self):
        files = []
        for p in sorted(RESULTS_DIR.glob("*.json"), reverse=True):
            try:
                data = json.loads(p.read_text())
                files.append({
                    "filename": p.name,
                    "timestamp": data.get("timestamp", ""),
                    "skill": data.get("skill", ""),
                    "mode": data.get("mode", data.get("eval_type", "")),
                    "total": data.get("total", 0),
                    "passed": data.get("passed", 0),
                    "pass_rate": data.get("pass_rate", data.get("accuracy", 0)),
                })
            except (json.JSONDecodeError, OSError):
                continue
        return files

    def _serve_result_file(self, filename):
        # Sanitize: only allow simple filenames
        if "/" in filename or "\\" in filename or ".." in filename:
            self._send(400, "text/plain", "Invalid filename")
            return
        filepath = RESULTS_DIR / filename
        if not filepath.exists():
            self._send(404, "text/plain", "File not found")
            return
        self._send(200, "application/json", filepath.read_text())

    def _send(self, code, content_type, body):
        if isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, code, data):
        self._send(code, "application/json", json.dumps(data))

    def log_message(self, format, *args):
        # Quieter logging
        pass


def main():
    port = PORT
    if "--port" in sys.argv:
        idx = sys.argv.index("--port")
        port = int(sys.argv[idx + 1])

    server = HTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}"
    print(f"Eval browser running at {url}")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()


if __name__ == "__main__":
    main()
