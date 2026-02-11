import os
import importlib
import sys
import json
from collections import deque
from datetime import datetime
from flask import Flask, request, Response, jsonify, render_template_string
import requests
import xml.etree.ElementTree as ET
import random
import string
import hashlib
import threading
import time
import concurrent.futures

from plugin_search_interface import PluginSearchBase
from plugin_download_interface import PluginDownloadBase
from newznab import searchresults_to_response
from sabnzbd import *
import health_monitor

# directory variables
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.environ.get('CONFIG') or os.path.join(BASE_DIR, "config")
CONFIG_DIR = os.path.abspath(CONFIG_DIR)
os.makedirs(CONFIG_DIR, exist_ok=True)
FLASK_PORT = os.environ.get("FLASK_RUN_PORT", "10000")
FLASK_HOST = os.environ.get("FLASK_RUN_HOST", "0.0.0.0")
PLUGIN_SEARCH_DIR = os.path.join(CONFIG_DIR, "plugins", "search")
PLUGIN_DOWNLOAD_DIR = os.path.join(CONFIG_DIR, "plugins", "download")
for directory in (PLUGIN_SEARCH_DIR, PLUGIN_DOWNLOAD_DIR):
    os.makedirs(directory, exist_ok=True)
DOWNLOAD_DIR = "/data/downloads/downloadarr"
SAB_API = "abcde"
SAB_CATEGORIES = ["lidarr"]

# array holding plugins
search_plugins = []
download_plugins = []
sabqueue = []
log_entries = deque(maxlen=200)
download_thread = None
_last_queue_report = None
initialization_lock = threading.Lock()
initialization_state = {
    "status": "starting",
    "message": "Loading configuration...",
    "search_ready": False,
    "download_ready": False,
    "queue_ready": False
}

# falsk app
app = Flask(__name__)

DASHBOARD_TEMPLATE = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Newznabarr Dashboard</title>
    <style>
      :root {
        --bg: #0b1120;
        --card: #111c2f;
        --card-alt: #15233d;
        --border: #1f2a44;
        --text: #e2e8f0;
        --muted: #8ea0c2;
        --accent: #38bdf8;
        --success: #2dd4bf;
        --warning: #facc15;
        --error: #f87171;
      }
      body {
        font-family: 'Inter', 'Segoe UI', sans-serif;
        margin: 0 auto;
        padding: 2rem;
        background: radial-gradient(circle at top, #142040 0%, #0b1120 55%);
        color: var(--text);
        max-width: 1400px;
        min-height: 100vh;
      }
      h1 {
        margin: 0 0 0.25rem;
        font-size: 2rem;
        font-weight: 600;
      }
      h2 {
        margin-top: 0;
        font-size: 1rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--muted);
      }
      a { color: var(--accent); }
      .summary {
        display: flex;
        gap: 1rem;
        flex-wrap: wrap;
        margin: 1rem 0 1.5rem;
      }
      .summary > div {
        background: var(--card);
        padding: 0.85rem 1.3rem;
        border-radius: 12px;
        border: 1px solid var(--border);
        min-width: 150px;
        box-shadow: 0 10px 35px rgba(10, 15, 35, 0.5);
      }
      .card {
        background: var(--card);
        border-radius: 14px;
        padding: 1.25rem 1.5rem;
        margin-top: 1.5rem;
        border: 1px solid var(--border);
        box-shadow: 0 25px 50px rgba(3, 5, 12, 0.65);
      }
      table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 0.8rem;
        border-radius: 12px;
        overflow: hidden;
        background: var(--card-alt);
      }
      th, td {
        padding: 0.75rem;
        text-align: left;
      }
      th {
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        background: #1b2a44;
        color: var(--muted);
      }
      tbody tr:nth-child(odd) { background: rgba(255,255,255,0.015); }
      tbody tr:hover { background: rgba(56, 189, 248, 0.07); }
      .status {
        padding: 0.25rem 0.65rem;
        border-radius: 999px;
        font-size: 0.8rem;
        font-weight: 600;
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
      }
      .status::before {
        content: '';
        width: 8px;
        height: 8px;
        border-radius: 50%;
        display: inline-block;
      }
      .Queued { background: rgba(109, 76, 239, 0.2); color: #c3b5ff; }
      .Queued::before { background: #c3b5ff; }
      .Downloading { background: rgba(16, 185, 129, 0.18); color: #34d399; }
      .Downloading::before { background: #34d399; }
      .Complete { background: rgba(59, 130, 246, 0.18); color: #93c5fd; }
      .Complete::before { background: #93c5fd; }
      .Failed { background: rgba(248, 113, 113, 0.2); color: #fecaca; }
      .Failed::before { background: #f87171; }
      .progress {
        width: 100%;
        background: #1f2a44;
        border-radius: 999px;
        overflow: hidden;
        height: 14px;
        margin-top: 0.2rem;
        box-shadow: inset 0 0 8px rgba(0,0,0,0.4);
      }
      .progress-bar {
        height: 100%;
        background: linear-gradient(90deg, #34d399, #38bdf8);
        text-align: right;
        font-size: 0.65rem;
        color: #0b1120;
        padding-right: 0.4rem;
        line-height: 14px;
        transition: width 0.3s ease;
        font-weight: 600;
      }
      .muted { color: var(--muted); }
      #system-status {
        display: flex;
        align-items: center;
        gap: 0.9rem;
        padding: 0.8rem 1rem;
        background: var(--card-alt);
        border-radius: 10px;
        border: 1px solid var(--border);
      }
      .status-dot {
        width: 12px;
        height: 12px;
        border-radius: 50%;
        display: inline-block;
      }
      .status-dot.ready { background: var(--success); }
      .status-dot.loading { background: var(--warning); }
      .status-dot.error { background: var(--error); }
      .status-dot.starting { background: #c084fc; }
      .status-dot.info { background: var(--accent); }
      .status-dot.success { background: var(--success); }
      .status-dot.warning { background: var(--warning); }
      .activity-list {
        max-height: 230px;
        overflow-y: auto;
        padding-right: 0.5rem;
      }
      .activity-entry {
        display: flex;
        align-items: center;
        gap: 0.8rem;
        padding: 0.45rem 0;
        border-bottom: 1px solid rgba(255,255,255,0.05);
      }
      .activity-entry:last-child { border-bottom: none; }
      .activity-message { flex: 1; }
      .activity-time { font-size: 0.8rem; color: var(--muted); white-space: nowrap; }
      .log-entry {
        font-family: 'JetBrains Mono', monospace;
        border-bottom: 1px solid rgba(255,255,255,0.08);
        padding: 0.4rem 0;
        color: #cbd5f5;
      }
      .log-entry:last-child { border-bottom: none; }
      #queue-table, #history-table { width: 100%; }
      @media (max-width: 900px) {
        body { padding: 1.5rem; }
        th, td { padding: 0.55rem; }
      }
    </style>
  </head>
  <body>
    <h1>Newznabarr Status</h1>
    <p>Last updated <span id="updated-at">{{ updated }}</span> | <a href="/settings" style="color: #2980b9;">⚙️ Settings</a></p>
    <div class="summary">
      <div><strong>Queue:</strong> <span id="queue-count">{{ queue_count }}</span></div>
      <div><strong>Completed:</strong> <span id="complete-count">{{ complete_count }}</span></div>
      <div><strong>Failed:</strong> <span id="failed-count">{{ failed_count }}</span></div>
    </div>

    <div class="card">
      <h2>System Status</h2>
      <div id="system-status">
        <span id="system-status-dot" class="status-dot {{ 'ready' if initialization.status == 'ready' else ('error' if initialization.status == 'error' else ('loading' if initialization.status == 'loading_plugins' else 'starting')) }}"></span>
        <div>
          <strong id="system-status-text">{{ initialization.status|replace('_', ' ')|title }}</strong>
          <div id="system-status-message" class="muted">{{ initialization.message }}</div>
        </div>
      </div>
    </div>

    <div class="card">
      <h2>Background Activity</h2>
      <div id="activity-list" class="activity-list">
        {% if background_activity %}
          {% for entry in background_activity %}
          <div class="activity-entry">
            <span class="status-dot {{ entry.status }}"></span>
            <div class="activity-message">{{ entry.message }}</div>
            <div class="activity-time">{{ entry.timestamp }}</div>
          </div>
          {% endfor %}
        {% else %}
          <p>Standing by...</p>
        {% endif %}
      </div>
    </div>

    <div class="card">
      <h2>Active Queue</h2>
      <table id="queue-table" {% if not queue %}style="display:none;"{% endif %}>
        <thead>
          <tr><th>Title</th><th>Category</th><th>Status</th><th>Progress</th><th>Speed</th><th>ETA</th></tr>
        </thead>
        <tbody id="queue-body">
        {% for item in queue %}
        <tr>
          <td>{{ item.title }}</td>
          <td>{{ item.cat }}</td>
          <td class="status {{ item.status|replace(' ', '') }}">{{ item.status }}</td>
          <td>
            {% if item.status == "Downloading" and item.progress is not none %}
            <div class="progress">
              <div class="progress-bar" style="width: {{ item.progress }}%">{{ item.progress }}%</div>
            </div>
            {% else %}
            <span class="muted">—</span>
            {% endif %}
          </td>
          <td>{{ item.speed_text or "—" }}</td>
          <td>{{ item.eta_text or "—" }}</td>
        </tr>
        {% endfor %}
        </tbody>
      </table>
      <p id="queue-empty" {% if queue %}style="display:none;"{% endif %}>No items in queue.</p>
    </div>

    <div class="card">
      <h2>History</h2>
      <table id="history-table" {% if not history %}style="display:none;"{% endif %}>
        <thead>
          <tr><th>Title</th><th>Status</th><th>Location</th></tr>
        </thead>
        <tbody id="history-body">
        {% for item in history %}
        <tr>
          <td>{{ item.title }}</td>
          <td class="status {{ item.status|replace(' ', '') }}">{{ item.status }}</td>
          <td>{{ item.storage or "Pending" }}</td>
        </tr>
        {% endfor %}
        </tbody>
      </table>
      <p id="history-empty" {% if history %}style="display:none;"{% endif %}>No completed or failed downloads yet.</p>
    </div>

    <div class="card">
      <h2>Plugin Health Status</h2>
      <div class="summary">
        <div><strong>Plugins:</strong> <span id="plugins-healthy">{{ health_summary.plugins.healthy }}</span>/<span id="plugins-total">{{ health_summary.plugins.total }}</span> healthy</div>
        <div style="color: #7f8c8d;"><strong>Disabled:</strong> <span id="plugins-disabled">{{ health_summary.plugins.disabled }}</span></div>
        <div style="color: #f39c12;"><strong>Warnings:</strong> <span id="plugins-warning">{{ health_summary.plugins.warning }}</span></div>
        <div style="color: #c0392b;"><strong>Errors:</strong> <span id="plugins-error">{{ health_summary.plugins.error }}</span></div>
      </div>
      <table style="margin-top: 1rem;">
        <thead>
          <tr><th>Plugin</th><th>Enabled</th><th>Search Status</th><th>Response Time</th><th>Download Status</th><th>Message</th></tr>
        </thead>
        <tbody id="plugin-health-body">
        {% for name, info in plugin_health.items() %}
        <tr>
          <td>{{ name }}</td>
          <td>
            {% if info.enabled %}
            <span style="color: #27ae60;">Yes</span>
            {% else %}
            <span style="color: #7f8c8d;">No</span>
            {% endif %}
          </td>
          <td><span style="color: {% if info.status == 'healthy' %}#27ae60{% elif info.status == 'warning' %}#f39c12{% elif info.status == 'disabled' %}#7f8c8d{% else %}#c0392b{% endif %};">● {{ info.status }}</span></td>
          <td>{{ info.response_time }}s</td>
          <td><span style="color: {% if info.download_status == 'healthy' %}#27ae60{% elif info.download_status == 'warning' %}#f39c12{% elif info.download_status == 'error' %}#c0392b{% elif info.download_status == 'disabled' %}#7f8c8d{% else %}#7f8c8d{% endif %};">● {{ info.download_status }}</span></td>
          <td>{{ info.message }} | {{ info.download_message }}</td>
        </tr>
        {% endfor %}
        </tbody>
      </table>

      <h3 style="margin-top: 2rem;">LibGen Mirrors</h3>
      <div class="summary">
        <div><strong>Mirrors:</strong> <span id="mirrors-healthy">{{ health_summary.mirrors.healthy }}</span>/<span id="mirrors-total">{{ health_summary.mirrors.total }}</span> healthy</div>
      </div>
      <table style="margin-top: 1rem;">
        <thead>
          <tr><th>Mirror</th><th>Status</th><th>Response Time</th><th>Message</th></tr>
        </thead>
        <tbody id="mirror-health-body">
        {% for url, info in mirror_health.items() %}
        <tr>
          <td>{{ url }}</td>
          <td><span style="color: {% if info.status == 'healthy' %}#27ae60{% elif info.status == 'warning' %}#f39c12{% else %}#c0392b{% endif %};">● {{ info.status }}</span></td>
          <td>{{ info.response_time }}s</td>
          <td>{{ info.message }}</td>
        </tr>
        {% endfor %}
        </tbody>
      </table>
    </div>

    <div class="card">
      <h2>Recent Events</h2>
      <div id="logs-container">
      {% if logs %}
        {% for entry in logs %}
          <div class="log-entry">{{ entry }}</div>
        {% endfor %}
      {% else %}
        <p>No log entries recorded.</p>
      {% endif %}
      </div>
    </div>
    <script>
      const STATUS_ENDPOINT = '/api/dashboard/status';
      const REFRESH_INTERVAL = 5000;

      function escapeHtml(value) {
        if (value === null || value === undefined) {
          return '';
        }
        return String(value)
          .replace(/&/g, '&amp;')
          .replace(/</g, '&lt;')
          .replace(/>/g, '&gt;')
          .replace(/"/g, '&quot;')
          .replace(/'/g, '&#39;');
      }

      function setText(id, value) {
        const el = document.getElementById(id);
        if (el) {
          el.textContent = value !== undefined && value !== null ? value : '';
        }
      }

      function renderInitialization(info) {
        if (!info) { return; }
        const statusText = (info.status || 'starting').replace(/_/g, ' ');
        setText('system-status-text', statusText.replace(/\b\w/g, char => char.toUpperCase()));
        setText('system-status-message', info.message || '');
        const dot = document.getElementById('system-status-dot');
        if (dot) {
          let dotClass = 'starting';
          if (info.status === 'ready') {
            dotClass = 'ready';
          } else if (info.status === 'error') {
            dotClass = 'error';
          } else if (info.status === 'loading_plugins') {
            dotClass = 'loading';
          }
          dot.className = `status-dot ${dotClass}`;
        }
      }

      function renderQueue(queue) {
        const table = document.getElementById('queue-table');
        const empty = document.getElementById('queue-empty');
        const tbody = document.getElementById('queue-body');
        if (!table || !empty || !tbody) { return; }
        if (!queue || queue.length === 0) {
          table.style.display = 'none';
          empty.style.display = 'block';
          tbody.innerHTML = '';
          return;
        }
        table.style.display = 'table';
        empty.style.display = 'none';
        const rows = queue.map(item => {
          const statusSafe = (item.status || '').replace(/\s+/g, '');
          const statusClass = `status ${escapeHtml(statusSafe)}`;
          const hasProgress = item.status === 'Downloading' && item.progress !== null && item.progress !== undefined;
          const pctValue = Number(item.progress);
          const safePct = Math.min(100, Math.max(0, Math.round(isNaN(pctValue) ? 0 : pctValue)));
          const progress = hasProgress
            ? `<div class="progress"><div class="progress-bar" style="width:${safePct}%">${safePct}%</div></div>`
            : '<span class="muted">—</span>';
          const speedText = item.speed_text ? escapeHtml(item.speed_text) : '—';
          const etaText = item.eta_text ? escapeHtml(item.eta_text) : '—';
          return `<tr>
            <td>${escapeHtml(item.title)}</td>
            <td>${escapeHtml(item.cat || '')}</td>
            <td class="${statusClass}">${escapeHtml(item.status)}</td>
            <td>${progress}</td>
            <td>${speedText}</td>
            <td>${etaText}</td>
          </tr>`;
        }).join('');
        tbody.innerHTML = rows;
      }

      function renderHistory(history) {
        const table = document.getElementById('history-table');
        const empty = document.getElementById('history-empty');
        const tbody = document.getElementById('history-body');
        if (!table || !empty || !tbody) { return; }
        if (!history || history.length === 0) {
          table.style.display = 'none';
          empty.style.display = 'block';
          tbody.innerHTML = '';
          return;
        }
        table.style.display = 'table';
        empty.style.display = 'none';
        tbody.innerHTML = history.map(item => {
          const statusSafe = (item.status || '').replace(/\s+/g, '');
          return `<tr>
            <td>${escapeHtml(item.title)}</td>
            <td class="status ${escapeHtml(statusSafe)}">${escapeHtml(item.status)}</td>
            <td>${escapeHtml(item.storage || 'Pending')}</td>
          </tr>`;
        }).join('');
      }

      function renderLogs(logs) {
        const container = document.getElementById('logs-container');
        if (!container) { return; }
        if (!logs || logs.length === 0) {
          container.innerHTML = '<p>No log entries recorded.</p>';
          return;
        }
        container.innerHTML = logs.map(entry => `<div class="log-entry">${escapeHtml(entry)}</div>`).join('');
      }

      function formatActivityTime(ts) {
        if (!ts) { return ''; }
        const date = new Date(ts);
        if (isNaN(date.getTime())) {
          return ts;
        }
        return date.toLocaleTimeString();
      }

      function renderActivity(activity) {
        const container = document.getElementById('activity-list');
        if (!container) { return; }
        if (!activity || activity.length === 0) {
          container.innerHTML = '<p>Standing by...</p>';
          return;
        }
        const html = activity.map(entry => {
          const statusMap = {
            success: 'success',
            error: 'error',
            warning: 'warning',
            info: 'info'
          };
          const statusClass = statusMap[entry.status] || 'info';
          return `<div class="activity-entry">
            <span class="status-dot ${statusClass}"></span>
            <div class="activity-message">${escapeHtml(entry.message)}</div>
            <div class="activity-time">${escapeHtml(formatActivityTime(entry.timestamp))}</div>
          </div>`;
        }).join('');
        container.innerHTML = html;
      }

      function renderHealth(summary, pluginHealth, mirrorHealth) {
        if (summary) {
          setText('plugins-healthy', summary.plugins.healthy);
          setText('plugins-total', summary.plugins.total);
          setText('plugins-disabled', summary.plugins.disabled);
          setText('plugins-warning', summary.plugins.warning);
          setText('plugins-error', summary.plugins.error);
          setText('mirrors-healthy', summary.mirrors.healthy);
          setText('mirrors-total', summary.mirrors.total);
        }
        const pluginBody = document.getElementById('plugin-health-body');
        if (pluginBody) {
          const rows = Object.entries(pluginHealth || {}).map(([name, info]) => {
            const statusColor = info.status === 'healthy' ? '#27ae60'
              : info.status === 'warning' ? '#f39c12'
              : info.status === 'disabled' ? '#7f8c8d'
              : '#c0392b';
            const downloadColor = info.download_status === 'healthy' ? '#27ae60'
              : info.download_status === 'warning' ? '#f39c12'
              : info.download_status === 'error' ? '#c0392b'
              : info.download_status === 'disabled' ? '#7f8c8d'
              : '#7f8c8d';
            const enabled = info.enabled ? '<span style="color: #27ae60;">Yes</span>' : '<span style="color: #7f8c8d;">No</span>';
            return `<tr>
              <td>${escapeHtml(name)}</td>
              <td>${enabled}</td>
              <td><span style="color:${statusColor};">● ${escapeHtml(info.status)}</span></td>
              <td>${escapeHtml(info.response_time)}s</td>
              <td><span style="color:${downloadColor};">● ${escapeHtml(info.download_status || 'unknown')}</span></td>
              <td>${escapeHtml(info.message || '')} | ${escapeHtml(info.download_message || '')}</td>
            </tr>`;
          }).join('');
          pluginBody.innerHTML = rows;
        }

        const mirrorBody = document.getElementById('mirror-health-body');
        if (mirrorBody) {
          const rows = Object.entries(mirrorHealth || {}).map(([url, info]) => {
            const color = info.status === 'healthy' ? '#27ae60' : info.status === 'warning' ? '#f39c12' : '#c0392b';
            return `<tr>
              <td>${escapeHtml(url)}</td>
              <td><span style="color:${color};">● ${escapeHtml(info.status)}</span></td>
              <td>${escapeHtml(info.response_time)}s</td>
              <td>${escapeHtml(info.message || '')}</td>
            </tr>`;
          }).join('');
          mirrorBody.innerHTML = rows;
        }
      }

      function updateDashboard(data) {
        if (!data) { return; }
        setText('queue-count', data.queue_count);
        setText('complete-count', data.complete_count);
        setText('failed-count', data.failed_count);
        setText('updated-at', data.updated);
        renderInitialization(data.initialization);
        renderQueue(data.queue);
        renderHistory(data.history);
        renderLogs(data.logs);
        renderHealth(data.health_summary, data.plugin_health, data.mirror_health);
        renderActivity(data.background_activity);
      }

      async function pollStatus() {
        try {
          const res = await fetch(STATUS_ENDPOINT);
          if (res.ok) {
            const data = await res.json();
            updateDashboard(data);
          }
        } catch (err) {
          console.error('Dashboard refresh failed', err);
        }
      }

      document.addEventListener('DOMContentLoaded', () => {
        pollStatus();
        setInterval(pollStatus, REFRESH_INTERVAL);
      });
    </script>
  </body>
</html>
"""

SETTINGS_TEMPLATE = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Newznabarr Settings</title>
    <style>
      body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f7; color: #1e1e24; }
      h1 { margin-bottom: 0.5rem; }
      h2 { margin-top: 2rem; border-bottom: 2px solid #e0e0e0; padding-bottom: 0.5rem; }
      .card { background: #fff; border-radius: 8px; padding: 1.5rem; box-shadow: 0 2px 5px rgba(0,0,0,0.05); margin-top: 1rem; }
      .setting-row { display: flex; justify-content: space-between; align-items: center; padding: 1rem 0; border-bottom: 1px solid #f0f0f0; }
      .setting-row:last-child { border-bottom: none; }
      .setting-label { font-weight: 500; }
      .setting-description { font-size: 0.9rem; color: #666; margin-top: 0.25rem; }
      .technical-info { font-size: 0.8rem; color: #e67e22; margin-top: 0.25rem; font-style: italic; }
      .toggle { position: relative; display: inline-block; width: 50px; height: 24px; }
      .toggle input { opacity: 0; width: 0; height: 0; }
      .slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: #ccc; transition: .4s; border-radius: 24px; }
      .slider:before { position: absolute; content: ""; height: 18px; width: 18px; left: 3px; bottom: 3px; background-color: white; transition: .4s; border-radius: 50%; }
      input:checked + .slider { background-color: #2196F3; }
      input:checked + .slider:before { transform: translateX(26px); }
      .status-enabled { color: #27ae60; font-weight: bold; }
      .status-disabled { color: #c0392b; font-weight: bold; }
      .btn { padding: 0.6rem 1.5rem; border: none; border-radius: 6px; cursor: pointer; font-size: 1rem; }
      .btn-primary { background: #2980b9; color: white; }
      .btn-primary:hover { background: #21618c; }
      .btn-secondary { background: #95a5a6; color: white; margin-left: 0.5rem; }
      .btn-secondary:hover { background: #7f8c8d; }
      input[type="text"], input[type="number"], textarea { padding: 0.5rem; border: 1px solid #ddd; border-radius: 4px; width: 250px; }
      textarea { width: 100%; min-height: 100px; font-family: monospace; }
      .message { padding: 1rem; border-radius: 6px; margin-top: 1rem; }
      .message-success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
      .message-error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
    </style>
    <script>
      function saveSettings() {
        const plugins = {};
        document.querySelectorAll('[data-plugin]').forEach(toggle => {
          plugins[toggle.dataset.plugin] = {enabled: toggle.checked};
        });
        
        const settings = {
          plugin_settings: plugins,
          download_directory: document.getElementById('download_dir').value,
          sab_api: document.getElementById('sab_api').value,
          sab_categories: document.getElementById('sab_categories').value.split(',').map(s => s.trim()),
          libgen_mirrors: document.getElementById('libgen_mirrors').value.split('\\n').map(s => s.trim()).filter(s => s)
        };
        
        fetch('/api/settings/save', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(settings)
        })
        .then(r => r.json())
        .then(data => {
          if (data.success) {
            showMessage('Settings saved! Changes apply immediately.', 'success');
          } else {
            showMessage('Error saving settings: ' + (data.error || 'Unknown error'), 'error');
          }
        })
        .catch(e => showMessage('Error: ' + e.message, 'error'));
      }
      
      function showMessage(text, type) {
        const msg = document.getElementById('message');
        msg.textContent = text;
        msg.className = 'message message-' + type;
        msg.style.display = 'block';
        setTimeout(() => msg.style.display = 'none', 5000);
      }
    </script>
  </head>
  <body>
    <h1>⚙️ Newznabarr Settings</h1>
    <p><a href="/" style="color: #2980b9;">← Back to Dashboard</a></p>
    
    <div id="message" style="display:none;"></div>
    
    <div class="card">
      <h2>Search Plugins</h2>
      <p>Enable or disable book search sources.</p>
      
      {% for plugin_id, plugin_info in plugins.items() %}
      <div class="setting-row">
        <div>
          <div class="setting-label">{{ plugin_info.name }}</div>
          <div class="setting-description">{{ plugin_info.description }}</div>
          <div class="technical-info">⚠️ {{ plugin_info.technical_info }}</div>
        </div>
        <label class="toggle">
          <input type="checkbox" data-plugin="{{ plugin_id }}" {% if plugin_info.enabled %}checked{% endif %}>
          <span class="slider"></span>
        </label>
      </div>
      {% endfor %}
    </div>
    
    <div class="card">
      <h2>Download Settings</h2>
      
      <div class="setting-row">
        <div>
          <div class="setting-label">Download Directory</div>
          <div class="setting-description">Where downloaded books will be stored</div>
        </div>
        <input type="text" id="download_dir" value="{{ download_directory }}">
      </div>
      
      <div class="setting-row">
        <div>
          <div class="setting-label">SAB API Key</div>
          <div class="setting-description">API key for SABnzbd compatibility</div>
        </div>
        <input type="text" id="sab_api" value="{{ sab_api }}">
      </div>
      
      <div class="setting-row">
        <div>
          <div class="setting-label">SAB Categories</div>
          <div class="setting-description">Comma-separated list of categories</div>
        </div>
        <input type="text" id="sab_categories" value="{{ sab_categories }}">
      </div>
    </div>
    
    <div class="card">
      <h2>LibGen Mirrors</h2>
      <p>One mirror URL per line. These are fallback mirrors for LibGen searches.</p>
      <textarea id="libgen_mirrors">{{ libgen_mirrors }}</textarea>
    </div>
    
    <div class="card" style="text-align: center;">
      <button class="btn btn-primary" onclick="saveSettings()">💾 Save Settings</button>
      <button class="btn btn-secondary" onclick="window.location.href='/'">Cancel</button>
    </div>
  </body>
</html>
"""


def log_event(message):
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp} UTC] {message}"
    log_entries.appendleft(entry)
    print(entry)


def update_initialization_state(**updates):
    with initialization_lock:
        initialization_state.update(updates)


def get_initialization_state():
    with initialization_lock:
        return dict(initialization_state)

# load all the search plugins
def load_search_plugins(search_plugin_directory, config=None):
    search_plugins = []
    if not os.path.isdir(search_plugin_directory):
        print(f"Search plugin directory '{search_plugin_directory}' not found.")
        return search_plugins

    # Get enabled plugins from config
    plugin_settings = config.get("plugin_settings", {}) if config else {}

    sys.path.insert(0, search_plugin_directory)
    print("Loading search plugins from:" + search_plugin_directory)

    for filename in os.listdir(search_plugin_directory):
        if filename.endswith(".py") and filename != "__init__.py":
            module_name = filename[:-3]
            
            # Check if plugin is enabled in config
            plugin_config = plugin_settings.get(module_name, {})
            # Default to False unless it's libgen which we default to True for backward compatibility if config is missing
            default_enabled = True if module_name == "libgen" else False
            is_enabled = plugin_config.get("enabled", default_enabled)
            
            try:
                module = importlib.import_module(module_name)
                for attr in dir(module):
                    obj = getattr(module, attr)
                    if isinstance(obj, type) and issubclass(obj, PluginSearchBase) and obj is not PluginSearchBase:
                        instance = obj()
                        instance.id = module_name
                        instance.enabled = is_enabled
                        search_plugins.append(instance)
                        if not is_enabled:
                            print(f"Loaded disabled plugin: {module_name}")
            except Exception as e:
                print(f"Failed to load plugin {module_name}: {e}")
    sys.path.pop(0)
    print("Loaded search plugins: " + str(len(search_plugins)))
    return search_plugins

def load_download_plugins(download_plugin_directory):
    download_plugins = []
    if not os.path.isdir(download_plugin_directory):
        print(f"Download plugin directory '{download_plugin_directory}' not found.")
        return download_plugins

    sys.path.insert(0, download_plugin_directory)
    print("Loading download plugins from:" + download_plugin_directory)

    for filename in os.listdir(download_plugin_directory):
        if filename.endswith(".py") and filename != "__init__.py":
            module_name = filename[:-3]
            try:
                module = importlib.import_module(module_name)
                for attr in dir(module):
                    obj = getattr(module, attr)
                    if isinstance(obj, type) and issubclass(obj, PluginDownloadBase) and obj is not PluginDownloadBase:
                        download_plugins.append(obj())
            except Exception as e:
                print(f"Failed to load plugin {module_name}: {e}")
    sys.path.pop(0)
    print("Loaded download plugins: " + str(len(download_plugins)))
    return download_plugins

def run_download_queue():
    log_event("Download queue worker started")
    global sabqueue
    global CONFIG_DIR
    global _last_queue_report
    while True:
        queue_len = len(sabqueue)
        if queue_len != _last_queue_report:
            log_event(f"Items in queue: {queue_len}")
            _last_queue_report = queue_len
        for dl in sabqueue:
            if dl['status'] == "Queued":
                dl["status"] = "Downloading"
                dl["progress"] = 0
                dl["bytes_downloaded"] = 0
                dl["speed_bps"] = 0
                start_time = time.time()
                sabsavequeue(CONFIG_DIR,sabqueue)
                handled = False
                size_hint = dl.get("bytes_total") or dl.get("size") or 0
                try:
                    size_hint = int(size_hint)
                except (TypeError, ValueError):
                    size_hint = 0

                def progress_callback(downloaded, total=None):
                    dl["bytes_downloaded"] = downloaded or 0
                    if total:
                        dl["bytes_total"] = total
                    elif size_hint:
                        dl["bytes_total"] = size_hint
                    total_bytes = dl.get("bytes_total") or 0
                    try:
                        total_bytes = int(total_bytes)
                    except (TypeError, ValueError):
                        total_bytes = 0
                    if total_bytes > 0:
                        dl["progress"] = min(100, max(0, int((dl["bytes_downloaded"] / total_bytes) * 100)))
                    else:
                        dl["progress"] = None
                    elapsed = max(time.time() - start_time, 0.001)
                    dl["speed_bps"] = dl["bytes_downloaded"] / elapsed

                for dlplugin in download_plugins:
                    if dl["prefix"] in dlplugin.getprefix():
                        log_event(f"Starting download for '{dl['title']}' via {dlplugin.__class__.__name__}")
                        result = dlplugin.download(dl["url"],dl["title"],DOWNLOAD_DIR,dl["cat"], progress_callback=progress_callback)
                        handled = True
                        if result == "404":
                            dl["status"] = "Failed"
                            dl["progress"] = None
                            dl["speed_bps"] = 0
                            log_event(f"Download failed for '{dl['title']}'")
                            sabsavequeue(CONFIG_DIR,sabqueue)
                        else:
                            dl["status"] = "Complete"
                            dl["storage"] = result
                            dl["progress"] = 100
                            dl["speed_bps"] = 0
                            log_event(f"Download completed: {result}")
                            sabsavequeue(CONFIG_DIR,sabqueue)
                        break
                if not handled:
                    dl["status"] = "Failed"
                    dl["progress"] = None
                    dl["speed_bps"] = 0
                    log_event(f"No downloader registered for prefix {dl['prefix']}")
                    sabsavequeue(CONFIG_DIR, sabqueue)
        time.sleep(1)


def ensure_download_worker():
    global download_thread
    if not get_initialization_state().get("download_ready"):
        return
    if download_thread and download_thread.is_alive():
        return
    download_thread = threading.Thread(target=run_download_queue)
    download_thread.daemon = True
    download_thread.start()

def read_config(config_file):
    try:
        with open(config_file, 'r') as file:
            config = json.load(file)  # Load the JSON data from the file
        return config
    except FileNotFoundError:
        print(f"Error: The file '{config_file}' was not found.")
        return None
    except json.JSONDecodeError:
        print(f"Error: The file '{config_file}' contains invalid JSON.")
        return None

def normalize_queue_entries():
    changed = False
    for dl in sabqueue:
        if "nzo" not in dl and dl.get("nzo_id"):
            dl["nzo"] = dl["nzo_id"]
            changed = True
        if "nzo_id" not in dl and dl.get("nzo"):
            dl["nzo_id"] = dl["nzo"]
            changed = True
        size_value = dl.get("size")
        try:
            size_int = int(size_value)
        except (TypeError, ValueError):
            size_int = 0
        dl["size"] = size_int
        if "bytes_total" not in dl:
            dl["bytes_total"] = size_int
            changed = True
        if "bytes_downloaded" not in dl:
            dl["bytes_downloaded"] = 0
            changed = True
        if dl.get("status") == "Downloading":
            dl["progress"] = dl.get("progress", 0)
        else:
            dl["progress"] = dl.get("progress", None)
        if "speed_bps" not in dl:
            dl["speed_bps"] = 0
    if changed:
        sabsavequeue(CONFIG_DIR, sabqueue)


def bootstrap_core():
    config = read_config(os.path.join(CONFIG_DIR, "config.json")) or {}
    global DOWNLOAD_DIR
    global SAB_API
    global SAB_CATEGORIES
    if config:
        DOWNLOAD_DIR = config.get("download_directory", DOWNLOAD_DIR)
        SAB_API = config.get("sab_api", SAB_API)
        SAB_CATEGORIES = config.get("sab_categories", SAB_CATEGORIES)
    log_event("Loading persistent queue")
    health_monitor.log_activity("Loading persistent queue", status="info")
    global sabqueue
    sabqueue = sabloadqueue(CONFIG_DIR)
    normalize_queue_entries()
    update_initialization_state(queue_ready=True, message="Queue loaded")
    health_monitor.log_activity("Queue ready", status="success")
    return config


def start_async(config):
    def runner():
        global search_plugins
        global download_plugins
        try:
            log_event("Loading search and download plugins")
            update_initialization_state(status="loading_plugins", message="Loading search plugins...")
            health_monitor.log_activity("Loading search plugins", status="info")
            search_plugins = load_search_plugins(PLUGIN_SEARCH_DIR, config)
            update_initialization_state(search_ready=True, message="Search plugins ready")
            health_monitor.log_activity("Search plugins ready", status="success")

            update_initialization_state(message="Loading download plugins...")
            health_monitor.log_activity("Loading download plugins", status="info")
            download_plugins = load_download_plugins(PLUGIN_DOWNLOAD_DIR)
            update_initialization_state(download_ready=True, message="Download plugins ready")
            health_monitor.log_activity("Download plugins ready", status="success")

            for dl in sabqueue:
                if dl["status"] == "Downloading":
                    dl["status"] = "Queued"
                    dl["progress"] = 0
                    dl["bytes_downloaded"] = 0
            sabsavequeue(CONFIG_DIR, sabqueue)

            ensure_download_worker()
            libgen_mirrors = config.get("libgen_mirrors", []) if config else []
            health_monitor.run_startup_health_checks(search_plugins, download_plugins, libgen_mirrors)
            update_initialization_state(status="ready", message="All systems operational")
            health_monitor.log_activity("System ready", status="success")
        except Exception as exc:
            log_event(f"Startup error: {exc}")
            update_initialization_state(status="error", message=str(exc))
            health_monitor.log_activity(f"Startup error: {exc}", status="error")

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()

# when api with t=caps, collect all supported cats from all search plugins
# and report them correctly
def newznab_caps_response():
    # Newznab category structure: parent categories with subcategories
    # Format: {parent_id: (parent_name, {subcat_id: subcat_name})}
    CATEGORY_STRUCTURE = {
        "7000": ("Books", {
            "7020": "eBook",
            "7010": "Magazines",
            "7030": "Comics",
            "7040": "Technical",
            "7050": "Other",
        }),
        "3000": ("Audio", {
            "3010": "MP3",
            "3020": "Audiobook",
            "3030": "Lossless",
            "3040": "Other",
        }),
    }
    
    root = ET.Element("caps")

    server = ET.SubElement(root, "server")
    server.set("version", "0.1")
    server.set("title", "Newznabarr")

    searching_node = ET.SubElement(root, "searching")
    ET.SubElement(searching_node, "search", available="yes", supportedParams="q,cat")

    supported_cats = set()
    for plugin in search_plugins:
        for cat in plugin.getcat():
            if cat is None:
                continue
            supported_cats.add(str(cat))

    if not supported_cats:
        # Always advertise at least standard book categories so indexers
        # can map this feed even if plugins fail to load at boot.
        supported_cats.update(["7020"])

    book_supported = any(cat in CATEGORY_STRUCTURE["7000"][1] for cat in supported_cats)
    music_supported = any(cat in CATEGORY_STRUCTURE["3000"][1] for cat in supported_cats)

    ET.SubElement(
        searching_node,
        "book-search",
        available="yes" if book_supported else "no",
        supportedParams="q,cat,author,title"
    )
    ET.SubElement(
        searching_node,
        "music-search",
        available="yes" if music_supported else "no",
        supportedParams="q,cat,artist,album"
    )

    categories_node = ET.SubElement(root, "categories")

    parent_elements = {}
    for cat_id in sorted(supported_cats):
        parent_id = None
        subcat_name = None

        for p_id, (p_name, subcats) in CATEGORY_STRUCTURE.items():
            if cat_id in subcats:
                parent_id = p_id
                subcat_name = subcats[cat_id]
                break

        if parent_id:
            if parent_id not in parent_elements:
                parent_elements[parent_id] = ET.SubElement(
                    categories_node,
                    "category",
                    id=parent_id,
                    name=CATEGORY_STRUCTURE[parent_id][0],
                    description=CATEGORY_STRUCTURE[parent_id][0],
                )
            ET.SubElement(
                parent_elements[parent_id],
                "subcat",
                id=cat_id,
                name=subcat_name,
                description=subcat_name,
            )
        else:
            # Fallback for unknown categories so they still appear in caps
            ET.SubElement(
                categories_node,
                "category",
                id=cat_id,
                name=f"Category {cat_id}",
                description=f"Category {cat_id}",
            )

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)

# flask routes and code

def calculate_progress(download_item):
    progress_value = download_item.get("progress")
    if progress_value is not None:
        return progress_value
    total = download_item.get("bytes_total")
    downloaded = download_item.get("bytes_downloaded")
    try:
        total = int(total)
        downloaded = int(downloaded)
    except (TypeError, ValueError):
        return None
    if total <= 0:
        return None
    return min(100, max(0, int((downloaded / total) * 100)))


def format_speed(bps):
    if not bps or bps <= 0:
        return ""
    units = ["B/s", "KiB/s", "MiB/s", "GiB/s"]
    value = float(bps)
    idx = 0
    while value >= 1024 and idx < len(units) - 1:
        value /= 1024
        idx += 1
    if idx == 0:
        return f"{int(value)} {units[idx]}"
    return f"{value:.1f} {units[idx]}"


def format_eta(seconds):
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes, sec = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {sec:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m"


def get_dashboard_snapshot():
    queue_snapshot = list(sabqueue)
    history_entries = [
        {
            "title": dl["title"],
            "status": dl["status"],
            "storage": dl.get("storage")
        }
        for dl in queue_snapshot if dl["status"] in ("Complete", "Failed")
    ]
    queue_display = []
    for dl in queue_snapshot:
        if dl["status"] in ("Queued", "Downloading"):
            eta_text = ""
            eta_seconds = None
            if dl["status"] == "Downloading":
                total = dl.get("bytes_total")
                downloaded = dl.get("bytes_downloaded")
                speed = dl.get("speed_bps")
                try:
                    total = int(total)
                    downloaded = int(downloaded)
                except (TypeError, ValueError):
                    total = None
                if total and downloaded is not None and speed and speed > 0 and total > downloaded:
                    remaining_secs = max((total - downloaded) / speed, 0)
                    eta_seconds = int(remaining_secs)
                    eta_text = format_eta(remaining_secs)

            queue_display.append({
                "title": dl["title"],
                "cat": dl["cat"],
                "status": dl["status"],
                "progress": calculate_progress(dl) if dl["status"] == "Downloading" else None,
                "bytes_total": dl.get("bytes_total"),
                "bytes_downloaded": dl.get("bytes_downloaded"),
                "prefix": dl.get("prefix"),
                "speed_text": format_speed(dl.get("speed_bps")),
                "speed_bps": dl.get("speed_bps") or 0,
                "eta_text": eta_text,
                "eta_seconds": eta_seconds
            })

    snapshot = {
        "queue": queue_display,
        "queue_count": len(queue_display),
        "history": history_entries[-20:][::-1],
        "complete_count": sum(1 for dl in queue_snapshot if dl["status"] == "Complete"),
        "failed_count": sum(1 for dl in queue_snapshot if dl["status"] == "Failed"),
        "logs": list(log_entries)[:50],
        "updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "health_summary": health_monitor.get_health_summary(),
        "plugin_health": health_monitor.plugin_health,
        "mirror_health": health_monitor.mirror_health,
        "initialization": get_initialization_state(),
        "background_activity": health_monitor.get_activity_log()
    }
    return snapshot


def render_dashboard():
    data = get_dashboard_snapshot()
    return render_template_string(
        DASHBOARD_TEMPLATE,
        **data
    )


@app.route("/")
def home():
    return render_dashboard()


@app.route("/queue")
def queue():
    return render_dashboard()


@app.route("/api/dashboard/status")
def dashboard_status():
    return jsonify(get_dashboard_snapshot())

@app.route("/settings")
def settings():
    """Render settings page"""
    config = read_config(os.path.join(CONFIG_DIR, "config.json")) or {}
    
    # Plugin information
    plugin_descriptions = {
        "libgen": {
            "name": "LibGen",
            "description": "Library Genesis - Largest collection of books and scientific articles",
            "technical_info": "Direct HTTP. Fast. No external dependencies.",
            "enabled": config.get("plugin_settings", {}).get("libgen", {}).get("enabled", True)
        },
        "annas_archive": {
            "name": "Anna's Archive",
            "description": "Aggregates LibGen, Z-Library and other sources",
            "technical_info": "Requires FlareSolverr. Slower due to browser emulation and heavy anti-bot protection.",
            "enabled": config.get("plugin_settings", {}).get("annas_archive", {}).get("enabled", False)
        },
        "openlibrary": {
            "name": "Open Library",
            "description": "10M+ books from Internet Archive - Legal and open",
            "technical_info": "Direct API. Fast. No external dependencies.",
            "enabled": config.get("plugin_settings", {}).get("openlibrary", {}).get("enabled", False)
        },
        "gutendex": {
            "name": "Project Gutenberg",
            "description": "75K+ classic public domain books",
            "technical_info": "Direct API. Fast. No external dependencies.",
            "enabled": config.get("plugin_settings", {}).get("gutendex", {}).get("enabled", False)
        },
        "standardebooks": {
            "name": "Standard Ebooks",
            "description": "High-quality formatted classics with modern typography",
            "technical_info": "Requires Selenium. Moderate speed. Uses browser automation for parsing.",
            "enabled": config.get("plugin_settings", {}).get("standardebooks", {}).get("enabled", False)
        },
        "manybooks": {
            "name": "ManyBooks",
            "description": "50K+ free books - Mix of public domain and author-permitted",
            "technical_info": "Requires FlareSolverr. Slow. Heavy Cloudflare protection requires full browser emulation.",
            "enabled": config.get("plugin_settings", {}).get("manybooks", {}).get("enabled", False)
        }
    }
    
    # Format libgen mirrors for display
    libgen_mirrors = config.get("libgen_mirrors", [])
    mirrors_text = "\n".join(libgen_mirrors)
    
    # Format SAB categories
    sab_cats = config.get("sab_categories", [])
    cats_text = ", ".join(sab_cats)
    
    return render_template_string(
        SETTINGS_TEMPLATE,
        plugins=plugin_descriptions,
        download_directory=config.get("download_directory", "/data/downloads/downloadarr"),
        sab_api=config.get("sab_api", "abcde"),
        sab_categories=cats_text,
        libgen_mirrors=mirrors_text
    )

@app.route("/api/settings/save", methods=["POST"])
def save_settings():
    """API endpoint to save settings"""
    try:
        new_settings = request.get_json()
        config_path = os.path.join(CONFIG_DIR, "config.json")
        
        # Read current config
        current_config = read_config(config_path) or {}
        
        # Update with new settings
        current_config["plugin_settings"] = new_settings.get("plugin_settings", {})
        current_config["download_directory"] = new_settings.get("download_directory", "/data/downloads/downloadarr")
        current_config["sab_api"] = new_settings.get("sab_api", "abcde")
        current_config["sab_categories"] = new_settings.get("sab_categories", [])
        current_config["libgen_mirrors"] = new_settings.get("libgen_mirrors", [])
        
        # Write config back
        # Write config back
        with open(config_path, 'w') as f:
            json.dump(current_config, f, indent=2)
            
        # Update loaded plugins in real-time
        plugin_settings = new_settings.get("plugin_settings", {})
        for plugin in search_plugins:
            if hasattr(plugin, 'id') and plugin.id in plugin_settings:
                plugin.enabled = plugin_settings[plugin.id].get("enabled", False)
                
        # Refresh health status
        health_monitor.check_all_plugins(search_plugins, download_plugins)
        
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api", methods=["GET", "POST"])
def api():
    global sabqueue

    mode = (request.args.get("mode") or request.form.get("mode") or "").strip().lower()
    query_type = (request.args.get("t") or "").strip().lower()
    download_action = (request.args.get("download") or "").strip().lower()

    # SABnzbd compatibility: mode=addurl
    # This is called when Readarr/Lidarr/etc. sends a download request
    if mode == "addurl":
        try:
            # Get parameters from either args or form
            name = request.args.get("name") or request.form.get("name")
            cat = request.args.get("cat") or request.form.get("cat") or ""
            priority = request.args.get("priority") or request.form.get("priority") or "-100"
            
            if not name:
                return jsonify({"status": False, "error": "Missing 'name' parameter"}), 400
            
            # Parse the NZB URL which contains our download metadata
            from urllib.parse import unquote, parse_qs, urlparse
            decoded_name = unquote(name)
            
            # Extract the actual download URL from the NZB URL
            parsed = urlparse(decoded_name)
            params = parse_qs(parsed.query)
            
            if 'url' not in params or 'prefix' not in params or 'title' not in params:
                return jsonify({"status": False, "error": "Invalid NZB URL format"}), 400
            
            url = params['url'][0]
            prefix = params['prefix'][0].strip()
            title = params['title'][0]
            size_param = params.get('size', ['0'])[0]
            try:
                size_bytes = int(size_param)
            except (TypeError, ValueError):
                size_bytes = 0
            
            # Add to queue
            ensure_download_worker()
            nzo_id = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
            
            sabqueue.append({
                "nzo_id": nzo_id,
                "nzo": nzo_id,
                "title": title,
                "url": url,
                "prefix": prefix,
                "cat": cat,
                "status": "Queued",
                "storage": None,
                "size": size_bytes,
                "bytes_total": size_bytes,
                "bytes_downloaded": 0,
                "progress": None,
                "speed_bps": 0,
                "created_at": datetime.utcnow().isoformat()
            })
            
            sabsavequeue(CONFIG_DIR, sabqueue)
            log_event(f"Added to queue: {title}")
            
            # Return SABnzbd-compatible response
            return jsonify({"status": True, "nzo_ids": [nzo_id]})
            
        except Exception as e:
            log_event(f"Error adding to queue: {e}")
            return jsonify({"status": False, "error": str(e)}), 500
    
    # return all cats supported by all our search plugins
    if query_type == "caps":
        xml_response = newznab_caps_response()
        return Response(xml_response, mimetype="application/xml")

    # readarr uses t=book to check if the indexer works
    # pretty sure this is for rss, so will have to implement rss later, fine for now
    # readarr uses t=book to check if the indexer works
    # pretty sure this is for rss, so will have to implement rss later, fine for now
    elif query_type == "book" :
        cat_param = request.args.get("cat")
        request_cats = cat_param.split(",") if cat_param else []
        all_results = []
        
        def search_plugin(plugin, cats):
            if not getattr(plugin, 'enabled', False):
                return []
            plugin_results = []
            for cat in plugin.getcat():
                if not cats or cat in cats:
                    query = plugin.gettestquery()
                    try:
                        res = plugin.search(query, cat)
                        if res:
                            plugin_results.extend(res)
                    except Exception as e:
                        print(f"Error in plugin {plugin}: {e}")
            return plugin_results

        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(search_plugin, p, request_cats) for p in search_plugins]
            for future in concurrent.futures.as_completed(futures):
                all_results.extend(future.result())
                
        xml_response = searchresults_to_response(request.host_url, all_results)
        return Response(xml_response, mimetype="application/xml")

    # lidarr uses t=music
    # if there is artist and album provided, it's a search
    # else it's probably rss feed
    # t=rss is for fetching RSS feeds (e.g. LibGen)
    elif query_type == "rss":
        all_results = []
        
        def fetch_rss_feed(plugin):
            if not getattr(plugin, 'enabled', False):
                return []
            if hasattr(plugin, 'get_rss_feed'):
                try:
                    return plugin.get_rss_feed()
                except Exception as e:
                    print(f"Error fetching RSS from {plugin}: {e}")
            return []

        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(fetch_rss_feed, p) for p in search_plugins]
            for future in concurrent.futures.as_completed(futures):
                all_results.extend(future.result())

        xml_response = searchresults_to_response(request.host_url, all_results)
        return Response(xml_response, mimetype="application/xml")

    # t=search is the normal search function

    # t=search is the normal search function
    # t=search is the normal search function
    elif query_type == "search" :
        cat_param = request.args.get("cat")
        request_cats = cat_param.split(",") if cat_param else []
        all_results = []
        query = request.args.get("q")
        
        # If no query is provided, treat it as an RSS sync request
        if not query:
            all_results = []
            def fetch_rss_feed_for_search(plugin):
                if not getattr(plugin, 'enabled', False):
                    return []
                if hasattr(plugin, 'get_rss_feed'):
                    try:
                        return plugin.get_rss_feed()
                    except Exception as e:
                        print(f"Error fetching RSS from {plugin}: {e}")
                return []

            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = [executor.submit(fetch_rss_feed_for_search, p) for p in search_plugins]
                for future in concurrent.futures.as_completed(futures):
                    all_results.extend(future.result())
            
            xml_response = searchresults_to_response(request.host_url, all_results)
            return Response(xml_response, mimetype="application/xml")

        # Otherwise, perform normal search
        query = query or "pride and prejudice" # Fallback should not be reached if logic above is correct, but keeping for safety if logic changes

        def search_general_plugin(plugin, cats, q):
            if not getattr(plugin, 'enabled', False):
                return []
            plugin_results = []
            for cat in plugin.getcat():
                if not cats or cat in cats:
                    try:
                        res = plugin.search(q, cat)
                        if res:
                            plugin_results.extend(res)
                    except Exception as e:
                        print(f"Error in plugin {plugin}: {e}")
            return plugin_results

        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(search_general_plugin, p, request_cats, query) for p in search_plugins]
            for future in concurrent.futures.as_completed(futures):
                all_results.extend(future.result())

        xml_response = searchresults_to_response(request.host_url, all_results)
        return Response(xml_response, mimetype="application/xml")


    # starr app downloads the nzb
    elif download_action == "nzb":


        # Create the root element with the required namespace
        nzb = ET.Element('nzb', xmlns="http://www.newzbin.com/DTD/2003/nzb")

        # Add a <meta> section to store the hidden URL in plain text
        meta = ET.SubElement(nzb, 'meta')
        url_element = ET.SubElement(meta, 'prefix')
        url_element.text = request.args.get("prefix")
        url_element = ET.SubElement(meta, 'url')
        url_element.text = request.args.get("url")
        url_element = ET.SubElement(meta, 'size')
        url_element.text = request.args.get("size")
        url_element = ET.SubElement(meta, 'title')
        url_element.text = request.args.get("title")

        # Create a <file> element with required attributes
        file_elem = ET.SubElement(nzb, 'file', poster="none", subject="none")
        
        # Add a <groups> section within the <file> element
        groups = ET.SubElement(file_elem, 'groups')
        group = ET.SubElement(groups, 'group')

        # Add a <segments> section with provided segments information
        segments = ET.SubElement(file_elem, 'segments')
        segment = ET.SubElement(segments, 'segment', bytes=request.args.get("size"), number="1")

        # Convert the XML tree to a string
        return ET.tostring(nzb, encoding='utf-8', xml_declaration=True).decode()    

    # sabnzbd functions
    elif mode == "version":
        return sabversion()

    elif mode == "get_config":
        if SAB_API == request.args.get("apikey"):
            sabconfig = sabgetconfig(SAB_CATEGORIES)
            sabconfig["config"]["misc"]["complete_dir"] = DOWNLOAD_DIR
            sabconfig["config"]["misc"]["api_key"] = SAB_API
            return sabconfig
        return jsonify({"error": "Access Denied"}), 403

    elif mode == "addfile":
        if SAB_API == request.args.get("apikey"):
            uploaded_file=request.files["name"]
            file_text = uploaded_file.read()
            root = ET.fromstring(file_text)
            namespace = {'nzb': 'http://www.newzbin.com/DTD/2003/nzb'}
            url_element = root.find('.//nzb:meta/nzb:url', namespace)
            url = url_element.text if url_element is not None else None
            prefix_element = root.find('.//nzb:meta/nzb:prefix', namespace)
            prefix = prefix_element.text if prefix_element is not None else None
            size_element = root.find('.//nzb:meta/nzb:size', namespace)
            size = size_element.text if size_element is not None else None
            title_element = root.find('.//nzb:meta/nzb:title', namespace)
            title = title_element.text if title_element is not None else None

            nzo=hashlib.md5(url.encode()).hexdigest()
            print(nzo)
            sabqueue.append({
                "prefix": prefix,
                "size": size,
                "url": url,
                "nzo": nzo,
                "title": title,
                "status": "Queued",
                "cat": request.args.get("cat")
            })
            log_event(f"Queued job '{title}' (cat: {request.args.get('cat')})")
            result=json.loads("""{"status":true,"nzo_ids":["SABnzbd_nzo_cqz8nwn8"]}""")
            result["nzo_ids"]=[f"SABnzbd_nzo_{nzo}"]
            sabsavequeue(CONFIG_DIR,sabqueue)
            return(result), 200
        return jsonify({"error": "Access Denied"}), 403

    elif mode == "queue":
        if SAB_API == request.args.get("apikey"):
            if "name" in request.args:
                if request.args.get("name") == "delete":
                    sabqueue = sabdeletefromqueue(CONFIG_DIR,sabqueue,request.args.get("value"))
                    return "ok"
            else:
                return sabgetqueue(sabqueue)
        return jsonify({"error": "Access Denied"}), 403

    elif mode == "history":
        if SAB_API == request.args.get("apikey"):
            if "name" in request.args:
                if request.args.get("name") == "delete":
                    sabqueue = sabdeletefromqueue(CONFIG_DIR,sabqueue,request.args.get("value"))
                    return "ok"
            else:
                return sabgethistory(sabqueue)
        return jsonify({"error": "Access Denied"}), 403

    log_event(f"Unknown /api request - mode='{mode}', t='{query_type}', download='{download_action}'")
    return jsonify({"status": False, "error": "Unsupported request"}), 400

_initial_config = bootstrap_core()
start_async(_initial_config)

if __name__ == "__main__":
    # start flask
    app.run(host=FLASK_HOST, port=FLASK_PORT)
