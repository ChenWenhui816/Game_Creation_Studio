'use strict';

const app = document.getElementById('app');
const toastEl = document.getElementById('toast');
const modal = document.getElementById('modal');
const modalTitle = document.getElementById('modal-title');
const modalBody = document.getElementById('modal-body');

const S = {
  state: null,
  stage: null,
  artifact: null,
  selected: null,
  dirty: false,
  preview: true,
  wizard: null,
  updateChecked: false,
  fillOpen: true,
  time: null,
  clockTimer: null,
};

const STATUS_LABEL = { drafting: '草稿', review: '待验收', frozen: '已冻结', blocked: '阻塞', change: '变更中' };
const GATE_LABEL = { pass: '通过', fail: '未通过', null: '未运行' };

function esc(value) {
  return String(value == null ? '' : value)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function toast(message, isError) {
  toastEl.hidden = false;
  toastEl.className = 'toast' + (isError ? ' err' : '');
  toastEl.textContent = message;
  clearTimeout(toast._timer);
  toast._timer = setTimeout(function () { toastEl.hidden = true; }, 3600);
}

function api(path, options) {
  options = options || {};
  const init = {
    method: options.method || 'GET',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
  };
  if (options.body !== undefined) init.body = JSON.stringify(options.body);
  return fetch(path, init).then(function (response) {
    return response.json().catch(function () { return { ok: false, error: '服务返回了非 JSON' }; });
  }).then(function (payload) {
    if (!payload || payload.ok !== true) {
      const error = new Error((payload && payload.error) || '请求失败');
      error.detail = payload && payload.detail;
      throw error;
    }
    return payload.data;
  });
}

function showError(error) {
  let text = error && error.message ? error.message : String(error);
  if (error && error.detail) {
    const d = error.detail;
    if (d.gate && d.gate.stdout_tail) text += '\n\n' + d.gate.stdout_tail;
    else if (d.stdout) text += '\n\n' + d.stdout;
  }
  toast(text, true);
}

function openModal(title, bodyHtml) {
  modalTitle.textContent = title;
  modalBody.innerHTML = bodyHtml;
  modal.hidden = false;
}
function closeModal() { modal.hidden = true; }
document.getElementById('modal-close').addEventListener('click', closeModal);
modal.addEventListener('click', function (event) { if (event.target === modal) closeModal(); });

function formatDuration(seconds) {
  const total = Math.max(0, Math.floor(seconds || 0));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  return (h ? h + 'h ' : '') + String(m).padStart(2, '0') + 'm ' + String(s).padStart(2, '0') + 's';
}

function pill(text, kind) {
  return '<span class="pill ' + (kind || '') + '">' + esc(text) + '</span>';
}

function stageKind(status) {
  if (status === 'frozen') return 'ok';
  if (status === 'review') return 'warn';
  if (status === 'blocked') return 'danger';
  if (status === 'change') return 'warn';
  return '';
}

/* ---------------- Markdown preview ---------------- */

function inlineMd(text) {
  let out = esc(text);
  out = out.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  out = out.replace(/\*([^*]+)\*/g, '<em>$1</em>');
  out = out.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>');
  out = out.replace(/\x60([^\x60]+)\x60/g, '<code>$1</code>');
  out = out.replace(/【待填】/g, '<mark class="fillable">【待填】</mark>');
  out = out.replace(/【示例】/g, '<span class="example">【示例】</span>');
  return out;
}

function tableHtml(lines) {
  const rows = lines.map(function (line) {
    return line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map(function (cell) { return cell.trim(); });
  });
  if (rows.length < 2) return '';
  let html = '<table>';
  html += '<thead><tr>' + rows[0].map(function (cell) { return '<th>' + inlineMd(cell) + '</th>'; }).join('') + '</tr></thead><tbody>';
  for (let i = 2; i < rows.length; i++) {
    html += '<tr>' + rows[i].map(function (cell) { return '<td>' + inlineMd(cell) + '</td>'; }).join('') + '</tr>';
  }
  return html + '</tbody></table>';
}

function mdToHtml(markdown) {
  const lines = String(markdown || '').replace(/\r\n/g, '\n').split('\n');
  const out = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (/^\s*$/.test(line)) { i++; continue; }
    if (/^\x60\x60\x60/.test(line)) {
      const buf = [];
      i++;
      while (i < lines.length && !/^\x60\x60\x60/.test(lines[i])) { buf.push(lines[i]); i++; }
      i++;
      out.push('<pre><code>' + esc(buf.join('\n')) + '</code></pre>');
      continue;
    }
    const heading = line.match(/^(#{1,6})\s+(.*)$/);
    if (heading) {
      const level = heading[1].length;
      out.push('<h' + level + ' class="md-locked" title="固定结构：请勿删除/改名">' + inlineMd(heading[2]) + '</h' + level + '>');
      i++;
      continue;
    }
    if (/^\s*>\s?/.test(line)) {
      const buf = [];
      while (i < lines.length && /^\s*>\s?/.test(lines[i])) {
        buf.push(lines[i].replace(/^\s*>\s?/, ''));
        i++;
      }
      out.push('<blockquote>' + inlineMd(buf.join(' ')) + '</blockquote>');
      continue;
    }
    if (/^\s*\|/.test(line) && i + 1 < lines.length && /^\s*\|?[\s:|-]+\|[\s:|-]*$/.test(lines[i + 1])) {
      const buf = [line, lines[i + 1]];
      i += 2;
      while (i < lines.length && /^\s*\|/.test(lines[i])) { buf.push(lines[i]); i++; }
      out.push(tableHtml(buf));
      continue;
    }
    if (/^\s*[-*]\s+/.test(line)) {
      const buf = [];
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
        buf.push('<li>' + inlineMd(lines[i].replace(/^\s*[-*]\s+/, '')) + '</li>');
        i++;
      }
      out.push('<ul>' + buf.join('') + '</ul>');
      continue;
    }
    if (/^\s*\d+\.\s+/.test(line)) {
      const buf = [];
      while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) {
        buf.push('<li>' + inlineMd(lines[i].replace(/^\s*\d+\.\s+/, '')) + '</li>');
        i++;
      }
      out.push('<ol>' + buf.join('') + '</ol>');
      continue;
    }
    if (/^\s*(---|\*\*\*|___)\s*$/.test(line)) { out.push('<hr>'); i++; continue; }
    const buf = [line];
    i++;
    while (i < lines.length && !/^\s*$/.test(lines[i]) &&
           !/^(#{1,6}\s|\x60\x60\x60|\s*\|)/.test(lines[i]) &&
           !/^\s*([-*]|\d+\.)\s+/.test(lines[i]) &&
           !/^\s*>/.test(lines[i])) {
      buf.push(lines[i]); i++;
    }
    out.push('<p>' + inlineMd(buf.join(' ')) + '</p>');
  }
  return out.join('\n');
}

/* ---------------- Shell ---------------- */

function renderTopbar() {
  const state = S.state;
  const project = state && state.project ? state.project : {};
  const current = state ? state.current_stage : '';
  const currentStage = state ? state.stages.find(function (s) { return s.id === current; }) : null;
  return '<header class="topbar">' +
    '<div class="brand"><div class="logo">GF</div><div>' +
    '<h1>' + esc(project.name || '制作控制台') + '</h1>' +
    '<div class="sub">' + esc(project.path || '本地单机 · 零依赖') + '</div>' +
    '</div></div>' +
    '<div class="top-actions">' +
    (currentStage ? pill('当前 ' + current + ' · ' + (STATUS_LABEL[currentStage.status] || ''), '') : '') +
    '<button class="btn" id="btn-dashboard">总览</button>' +
    '<span class="timer"><span id="time-clock">' + formatDuration(S.time ? (S.time.active ? S.time.active_elapsed + (S.time.total || 0) : S.time.total) : 0) + '</span>' +
    '<button class="btn tiny" id="btn-timer">' + (S.time && S.time.active ? '停止计时' : '开始计时') + '</button></span>' +
    '<button class="btn" id="btn-inbox">收件箱' + (state && state.pending_submissions ? ' ' + state.pending_submissions : '') + '</button>' +
    '<button class="btn" id="btn-changes">变更单' + (state && state.pending_changes ? ' ' + state.pending_changes : '') + '</button>' +
    '<button class="btn" id="btn-evidence">证据墙</button>' +
    '<button class="btn" id="btn-new">新建项目</button>' +
    '<button class="btn" id="btn-update">检查更新</button>' +
    '<button class="btn" id="btn-refresh">刷新</button>' +
    '</div></header>';
}

function renderSidebar() {
  let html = '<aside class="sidebar"><div class="stage-rail">';
  S.state.stages.forEach(function (stage) {
    const active = S.stage && S.stage.stage && S.stage.stage.id === stage.id;
    html += '<button class="stage-item ' + (active ? 'active' : '') + '" data-stage="' + stage.id + '">' +
      '<span class="stage-dot ' + stage.status + '"></span><span class="meta"><strong>' + stage.id + ' ' + esc(stage.name) + '</strong>' +
      '<span>' + STATUS_LABEL[stage.status] + ' · ' + esc(stage.gate_label) + '</span></span></button>';
  });
  html += '</div><div class="side-note">阶段文件夹：<br><b>stages/' + esc((S.stage && S.stage.folder) || '...') + '</b><br><br>文档仍在 docs/，这里是可本地阅读的版本与冻结快照。</div></aside>';
  return html;
}

function renderShell() {
  app.innerHTML = renderTopbar() + '<div class="layout">' + renderSidebar() + '<main class="main" id="main"></main></div>';
  document.querySelectorAll('[data-stage]').forEach(function (button) {
    button.addEventListener('click', function () {
      if (!confirmLeave()) return;
      location.hash = '#/stage/' + button.getAttribute('data-stage');
    });
  });
  const inbox = document.getElementById('btn-inbox');
  if (inbox) inbox.addEventListener('click', function () { location.hash = '#/inbox'; });
  const createNew = document.getElementById('btn-new');
  if (createNew) createNew.addEventListener('click', function () { location.hash = '#/new'; });
  const changes = document.getElementById('btn-changes');
  if (changes) changes.addEventListener('click', openChanges);
  const evidence = document.getElementById('btn-evidence');
  if (evidence) evidence.addEventListener('click', openEvidence);
  const refresh = document.getElementById('btn-refresh');
  if (refresh) refresh.addEventListener('click', function () { boot(); });
  const update = document.getElementById('btn-update');
  if (update) update.addEventListener('click', checkUpdate);
  const dashboard = document.getElementById('btn-dashboard');
  if (dashboard) dashboard.addEventListener('click', function () { location.hash = '#/dashboard'; });
  const timer = document.getElementById('btn-timer');
  if (timer) timer.addEventListener('click', toggleTimer);
}

function checkUpdate() {
  toast('正在检查 GitHub 版本…');
  api('/api/update').then(function (info) {
    if (!info.ok) { toast('检查失败：' + (info.error || '网络不可用'), true); return; }
    const state = info.update_available ? '发现新版本' : '已是最新';
    let body = '<div class="kv"><span>当前</span><b>' + esc(info.current) + '</b><span>最新</span><b>' + esc(info.latest || '—') + '</b></div>' +
      '<p style="margin-top:12px">下载地址：<a href="' + esc(info.url) + '" target="_blank" rel="noreferrer">' + esc(info.url) + '</a></p>';
    if (info.update_available && info.asset) {
      body += '<div class="btn-row" style="margin-top:14px"><button class="btn primary" id="btn-download-update">下载并安装</button></div>' +
        '<p class="tag">下载后需要重启 App 完成替换；项目文件不受影响。</p>';
    } else {
      body += '<p class="tag">更新只提示，不自动覆盖项目文件。</p>';
    }
    openModal('版本检查 · ' + state, body);
    const download = document.getElementById('btn-download-update');
    if (download) download.addEventListener('click', downloadUpdate);
  }).catch(showError);
}

function autoCheckUpdate() {
  api('/api/update').then(function (info) {
    if (info.ok && info.update_available) {
      toast('发现新版本 v' + info.latest + '，点右上角「检查更新」下载');
    }
  }).catch(function () { /* 启动检查静默失败 */ });
}

function downloadUpdate() {
  toast('正在下载更新包…');
  api('/api/update/download', { method: 'POST' }).then(function (info) {
    openModal('更新已下载',
      '<div class="kv"><span>版本</span><b>' + esc(info.version || '') + '</b><span>文件</span><b>' + esc(info.zip || '') + '</b></div>' +
      '<p style="margin-top:12px">安装会退出 App、替换程序并自动重启。</p>' +
      '<div class="btn-row"><button class="btn primary" id="btn-apply-update">立即重启更新</button></div>');
    const apply = document.getElementById('btn-apply-update');
    if (apply) apply.addEventListener('click', applyUpdate);
  }).catch(showError);
}

function applyUpdate() {
  if (!confirm('现在退出并安装更新？未保存的文档修改会丢失。')) return;
  toast('正在退出并安装更新…');
  api('/api/update/apply', { method: 'POST' }).then(function () {
    toast('App 即将重启，请稍候');
  }).catch(showError);
}


function changeStatusLabel(status) {
  return ({ pending: '待审批', approved: '已批准', rejected: '已拒绝', applied: '已生效' })[status] || status;
}

function openChanges() {
  api('/api/changes').then(function (data) {
    const items = data.items || [];
    const stages = (S.state && S.state.stages) || [];
    const options = stages.map(function (stage) {
      return '<option value="' + esc(stage.id) + '"' + (S.state && stage.id === S.state.current_stage ? ' selected' : '') + '>' +
        esc(stage.id + ' · ' + stage.name) + '</option>';
    }).join('');
    const list = items.length ? items.slice().reverse().map(function (item) {
      return '<li class="change-item"><div><b>' + esc(item.id) + '</b> · ' + esc(item.stage) + ' · ' + esc(item.title) +
        '<div class="tag">' + esc(changeStatusLabel(item.status)) + ' · ' + esc(item.at) + '</div>' +
        (item.reason ? '<p>' + esc(item.reason) + '</p>' : '') + '</div>' +
        '<div class="btn-row">' +
        ((item.baseline_docs && item.baseline_docs.length) ? '<button class="btn tiny" data-diff="' + esc(item.id) + '">查看 diff</button>' : '') +
        (item.status === 'pending' ? '<button class="btn tiny" data-approve="' + esc(item.id) + '">批准</button>' +
          '<button class="btn tiny" data-reject="' + esc(item.id) + '">拒绝</button>' : '') + '</div></li>';
    }).join('') : '<li class="empty">暂无变更单</li>';
    openModal('变更单',
      '<div class="change-form"><label>阶段</label><select id="change-stage">' + options + '</select>' +
      '<label>标题</label><input id="change-title" placeholder="例如：P1 增加双输入验收">' +
      '<label>原因</label><textarea id="change-reason" rows="3" placeholder="为什么改、影响哪些文档/资产"></textarea>' +
      '<label>影响文档（可选，逗号分隔）</label><input id="change-docs" placeholder="docs/02_美术圣经.md">' +
      '<div class="btn-row"><button class="btn primary" id="btn-create-change">创建变更单</button></div></div>' +
      '<h4 style="margin-top:18px">最近变更单</h4><ul class="change-list">' + list + '</ul>');
    const create = document.getElementById('btn-create-change');
    if (create) create.addEventListener('click', function () {
      const docs = (document.getElementById('change-docs').value || '').split(/[,，\n]/).map(function (x) { return x.trim(); }).filter(Boolean);
      api('/api/change/create', { method: 'POST', body: {
        stage: document.getElementById('change-stage').value,
        title: document.getElementById('change-title').value,
        reason: document.getElementById('change-reason').value,
        docs: docs
      }}).then(function () { toast('变更单已创建'); closeModal(); boot(); }).catch(showError);
    });
    modalBody.querySelectorAll('[data-approve]').forEach(function (button) {
      button.addEventListener('click', function () {
        if (!confirm('批准后该阶段会进入“变更中”，可修改文档；冻结时生效。')) return;
        api('/api/change/approve', { method: 'POST', body: { id: button.getAttribute('data-approve') } })
          .then(function () { toast('变更单已批准'); closeModal(); boot(); }).catch(showError);
      });
    });
    modalBody.querySelectorAll('[data-diff]').forEach(function (button) {
      button.addEventListener('click', function () { openChangeDiff(button.getAttribute('data-diff')); });
    });
    modalBody.querySelectorAll('[data-reject]').forEach(function (button) {
      button.addEventListener('click', function () {
        const reason = prompt('拒绝原因（可空）') || '';
        api('/api/change/reject', { method: 'POST', body: { id: button.getAttribute('data-reject'), reason: reason } })
          .then(function () { toast('已拒绝'); closeModal(); boot(); }).catch(showError);
      });
    });
  }).catch(showError);
}

function openEvidence() {
  api('/api/evidence').then(function (data) {
    const items = data.items || [];
    let html = '<p class="tag">目录：' + esc(data.folder || 'docs/evidence') + ' · ' + items.length + ' 个文件</p>' +
      '<div class="evidence-upload" id="evidence-drop"><b>拖拽截图/录屏到这里</b><span>或点击选择文件（单文件 ≤ 6 MB）</span>' +
      '<input type="file" id="evidence-file" multiple accept="image/*,video/*,.txt,.log,.json"></div>';
    if (!items.length) {
      html += '<div class="empty">还没有证据。上传截图、录屏或日志，方便验收。</div>';
    } else {
      html += '<div class="gallery">' + items.map(function (item) {
        const src = '/api/evidence/file?path=' + encodeURIComponent(item.path);
        const preview = item.kind === 'image' ? '<img src="' + esc(src) + '" loading="lazy" alt="">' :
          (item.kind === 'video' ? '<video src="' + esc(src) + '" controls preload="metadata"></video>' : '<div class="file-icon">FILE</div>');
        return '<a class="gallery-item" href="' + esc(src) + '" target="_blank" rel="noreferrer">' + preview +
          '<span>' + esc(item.name) + '</span><small>' + esc(item.mtime.replace('T', ' ')) + '</small></a>';
      }).join('') + '</div>';
    }
    openModal('证据墙', html);
    const input = document.getElementById('evidence-file');
    const drop = document.getElementById('evidence-drop');
    if (input) input.addEventListener('change', function () { uploadEvidence(input.files); });
    if (drop) {
      drop.addEventListener('dragover', function (event) { event.preventDefault(); drop.classList.add('over'); });
      drop.addEventListener('dragleave', function () { drop.classList.remove('over'); });
      drop.addEventListener('drop', function (event) {
        event.preventDefault();
        drop.classList.remove('over');
        if (event.dataTransfer && event.dataTransfer.files) uploadEvidence(event.dataTransfer.files);
      });
    }
  }).catch(showError);
}

function uploadEvidence(files) {
  const list = Array.from(files || []).filter(function (file) { return file.size <= 6 * 1024 * 1024; });
  if (!list.length) { toast('没有可上传文件（或文件超过 6 MB）', true); return; }
  toast('正在上传 ' + list.length + ' 个文件…');
  let chain = Promise.resolve(0);
  list.forEach(function (file) {
    chain = chain.then(function (done) {
      return new Promise(function (resolve, reject) {
        const reader = new FileReader();
        reader.onload = function () {
          const data = String(reader.result || '').split(',')[1] || '';
          api('/api/evidence/upload', { method: 'POST', body: {
            name: file.name, data: data, stage: S.state ? S.state.current_stage : ''
          }}).then(function () { resolve(done + 1); }).catch(reject);
        };
        reader.onerror = reject;
        reader.readAsDataURL(file);
      });
    });
  });
  chain.then(function (count) {
    toast('已上传 ' + count + ' 个证据');
    openEvidence();
  }).catch(showError);
}


function openChangeDiff(changeId) {
  api('/api/change/diff?id=' + encodeURIComponent(changeId)).then(function (data) {
    const docs = data.docs || [];
    let html = '<div class="kv"><span>变更单</span><b>' + esc(data.id) + '</b><span>状态</span><b>' + esc(changeStatusLabel(data.status)) + '</b></div>';
    if (!docs.length) {
      html += '<div class="empty">还没有可对比的基线（批准变更后才会保存）。</div>';
    } else {
      html += docs.map(function (doc) {
        const lines = String(doc.diff || '').split('\n').map(function (line) {
          let cls = '';
          if (line.startsWith('+++') || line.startsWith('---') || line.startsWith('@@')) cls = 'hunk';
          else if (line.startsWith('+')) cls = 'add';
          else if (line.startsWith('-')) cls = 'del';
          return '<span class="' + cls + '">' + esc(line || ' ') + '</span>';
        }).join('\n');
        return '<h4 style="margin-top:14px">' + esc(doc.path) + ' <small>+' + doc.added + ' / -' + doc.removed + '</small></h4>' +
          '<pre class="diff-view">' + (lines || '无差异') + '</pre>';
      }).join('');
    }
    openModal('变更单 diff', html);
  }).catch(showError);
}

/* ---------------- Outline / hierarchy ---------------- */

function renderOutline(markdown) {
  const box = document.getElementById('outline');
  if (!box) return;
  const editor = document.getElementById('editor');
  const lines = String(markdown || '').replace(/\r\n/g, '\n').split('\n');
  const h2 = [];
  lines.forEach(function (line, index) { if (/^##\s+/.test(line)) h2.push(index); });
  const rows = [];
  let section = -1;
  lines.forEach(function (line, index) {
    if (/^##\s+/.test(line)) section += 1;
    const heading = line.match(/^(#{2,3})\s+(.+)$/);
    if (heading) rows.push({ kind: 'heading', level: heading[1].length, text: heading[2].trim(), line: index, section: heading[1].length === 2 ? section : -1 });
    const check = line.match(/^\s*-\s+\[([ xX])\]\s+(.+)$/);
    if (check) rows.push({ kind: 'check', checked: check[1].toLowerCase() === 'x', text: check[2].trim(), line: index });
  });
  if (!rows.length) { box.innerHTML = '<div class="empty">当前文档没有 H2/H3 或检查项</div>'; return; }
  box.innerHTML = rows.map(function (row) {
    if (row.kind === 'heading') {
      const drag = row.section >= 0 ? ' draggable="true" data-section="' + row.section + '"' : '';
      return '<button class="outline-item level' + row.level + '" data-line="' + row.line + '"' + drag + '>' +
        (row.section >= 0 ? '<span class="drag-handle">⋮⋮</span>' : '') + esc(row.text) + '</button>';
    }
    return '<button class="outline-check" data-check-line="' + row.line + '">' +
      '<span class="check-mark">' + (row.checked ? '☑' : '☐') + '</span>' + esc(row.text) + '</button>';
  }).join('');
  box.querySelectorAll('[data-line]').forEach(function (button) {
    button.addEventListener('click', function () { scrollToLine(parseInt(button.getAttribute('data-line'), 10)); });
    if (button.getAttribute('draggable') === 'true') {
      button.addEventListener('dragstart', function (event) {
        event.dataTransfer.setData('text/plain', button.getAttribute('data-section'));
        event.dataTransfer.effectAllowed = 'move';
        button.classList.add('dragging');
      });
      button.addEventListener('dragend', function () { button.classList.remove('dragging'); });
      button.addEventListener('dragover', function (event) { event.preventDefault(); });
      button.addEventListener('drop', function (event) {
        event.preventDefault();
        const from = parseInt(event.dataTransfer.getData('text/plain'), 10);
        const to = parseInt(button.getAttribute('data-section'), 10);
        if (!isNaN(from) && !isNaN(to) && from !== to) reorderSection(from, to);
      });
    }
  });
  box.querySelectorAll('[data-check-line]').forEach(function (button) {
    button.addEventListener('click', function () { toggleCheckLine(parseInt(button.getAttribute('data-check-line'), 10)); });
  });
  const addButtons = box.parentElement.querySelectorAll('.outline-tools .btn');
  addButtons.forEach(function (button) { button.disabled = !editor || editor.disabled; });
}

function reorderSection(from, to) {
  const editor = document.getElementById('editor');
  if (!editor || editor.disabled) return;
  const lines = editor.value.replace(/\r\n/g, '\n').split('\n');
  const starts = [];
  lines.forEach(function (line, index) { if (/^##\s+/.test(line)) starts.push(index); });
  if (from < 0 || to < 0 || from >= starts.length || to >= starts.length) return;
  const sections = starts.map(function (start, index) { return lines.slice(start, index + 1 < starts.length ? starts[index + 1] : lines.length); });
  const prefix = lines.slice(0, starts[0]);
  const moved = sections.splice(from, 1)[0];
  sections.splice(to, 0, moved);
  editor.value = prefix.concat.apply(prefix, sections).join('\n');
  S.dirty = true;
  const preview = document.getElementById('preview');
  if (preview) preview.innerHTML = mdToHtml(editor.value);
  renderOutline(editor.value);
  toast('章节顺序已调整，保存后写入版本');
}

function scrollToLine(index) {
  const editor = document.getElementById('editor');
  if (!editor) return;
  const lines = editor.value.split('\n');
  let pos = 0;
  for (let i = 0; i < index && i < lines.length; i++) pos += lines[i].length + 1;
  editor.focus();
  editor.setSelectionRange(pos, pos);
  editor.scrollTop = Math.max(0, (index - 3) * 20);
}

function toggleCheckLine(index) {
  const editor = document.getElementById('editor');
  if (!editor || editor.disabled) return;
  const lines = editor.value.split('\n');
  if (index < 0 || index >= lines.length) return;
  lines[index] = lines[index].replace(/^(\s*-\s+\[)([ xX])(\])/, function (all, left, mark, right) {
    return left + (mark.toLowerCase() === 'x' ? ' ' : 'x') + right;
  });
  editor.value = lines.join('\n');
  S.dirty = true;
  const preview = document.getElementById('preview');
  if (preview) preview.innerHTML = mdToHtml(editor.value);
  renderOutline(editor.value);
}

function addSection() {
  const editor = document.getElementById('editor');
  if (!editor || editor.disabled) return;
  const title = prompt('新章节标题（会追加到文档末尾）');
  if (!title || !title.trim()) return;
  editor.value = editor.value.replace(/\s*$/, '') + '\n\n## ' + title.trim() + '\n\n';
  S.dirty = true;
  const preview = document.getElementById('preview');
  if (preview) preview.innerHTML = mdToHtml(editor.value);
  renderOutline(editor.value);
  toast('已追加章节，保存后写入版本');
}

function addCheckItem() {
  const editor = document.getElementById('editor');
  if (!editor || editor.disabled) return;
  const text = prompt('检查项文字（会追加到文档末尾）');
  if (!text || !text.trim()) return;
  editor.value = editor.value.replace(/\s*$/, '') + '\n- [ ] ' + text.trim() + '\n';
  S.dirty = true;
  const preview = document.getElementById('preview');
  if (preview) preview.innerHTML = mdToHtml(editor.value);
  renderOutline(editor.value);
  toast('已追加检查项，保存后写入版本');
}


function updateTimerUI() {
  const clock = document.getElementById('time-clock');
  const button = document.getElementById('btn-timer');
  if (!clock) return;
  const active = S.time && S.time.active;
  let elapsed = 0;
  if (active && active.start) {
    const started = new Date(active.start).getTime();
    if (!isNaN(started)) elapsed = Math.max(0, Math.floor((Date.now() - started) / 1000));
  }
  const seconds = (S.time ? (S.time.total || 0) : 0) + elapsed;
  clock.textContent = formatDuration(seconds);
  if (button) button.textContent = active ? '停止计时' : '开始计时';
}

function toggleTimer() {
  if (!S.state || !S.state.project) return;
  const active = S.time && S.time.active;
  const body = active ? {} : { stage: S.state.current_stage, note: '制作计时' };
  api(active ? '/api/time/stop' : '/api/time/start', { method: 'POST', body: body }).then(function (time) {
    S.time = time;
    updateTimerUI();
    toast(active ? '计时已停止' : '开始计时 · ' + S.state.current_stage);
    if (location.hash === '#/dashboard') renderDashboard();
  }).catch(showError);
}

function renderDashboard() {
  api('/api/time').then(function (time) {
    S.time = time;
    const state = S.state;
    renderShell();
    const main = document.getElementById('main');
    const stages = state.stages || [];
    const frozen = stages.filter(function (s) { return s.status === 'frozen'; }).length;
    const passed = stages.filter(function (s) { return s.gate_status === 'pass'; }).length;
    const totalDocs = stages.reduce(function (n, s) { return n + (s.docs || []).filter(function (d) { return d.exists; }).length; }, 0);
    const totalSeconds = time.total || 0;
    const ring = Math.round((frozen / stages.length) * 100);
    const circumference = 2 * Math.PI * 52;
    const dash = circumference * (frozen / stages.length);
    const stageBars = stages.map(function (stage) {
      const seconds = (time.per_stage || {})[stage.id] || 0;
      const width = totalSeconds ? Math.max(2, Math.round((seconds / totalSeconds) * 100)) : 0;
      return '<div class="bar-row"><span>' + esc(stage.id + ' ' + stage.name) + '</span>' +
        '<div class="bar-track"><i style="width:' + width + '%"></i></div><b>' + formatDuration(seconds) + '</b></div>';
    }).join('');
    const recent = (time.entries || []).slice(-6).reverse().map(function (entry) {
      return '<tr><td>' + esc(entry.stage) + '</td><td>' + esc((entry.start || '').replace('T', ' ')) + '</td><td>' + formatDuration(entry.seconds) + '</td><td>' + esc(entry.note || '') + '</td></tr>';
    }).join('');
    main.innerHTML =
      '<div class="page-head"><div><h2>制作总览</h2><p>阶段、闸门、文档与制作时间的单一视图。</p></div><div class="btn-row"><button class="btn" id="dash-stage">返回阶段</button></div></div>' +
      '<div class="dash-grid">' +
      '<section class="card dash-hero"><div class="ring-wrap"><svg viewBox="0 0 120 120"><circle class="ring-bg" cx="60" cy="60" r="52"></circle>' +
      '<circle class="ring-fg" cx="60" cy="60" r="52" stroke-dasharray="' + dash + ' ' + circumference + '"></circle>' +
      '<text x="60" y="58" text-anchor="middle" class="ring-num">' + ring + '%</text><text x="60" y="76" text-anchor="middle" class="ring-sub">阶段完成</text></svg></div>' +
      '<div class="dash-stats"><div><b>' + frozen + '</b><span>已冻结阶段</span></div><div><b>' + passed + '</b><span>闸门通过</span></div><div><b>' + totalDocs + '</b><span>已有文档</span></div><div><b>' + formatDuration(totalSeconds) + '</b><span>累计制作</span></div></div></section>' +
      '<section class="card"><h3>制作时间 · 按阶段</h3><div class="bars">' + (stageBars || '<div class="empty">还没有计时记录</div>') + '</div><p class="tag">用右上角「开始计时 / 停止计时」记录真实投入。</p></section>' +
      '<section class="card"><h3>阶段状态</h3><div class="stage-table">' + stages.map(function (s) {
        return '<div class="stage-row"><span class="dot ' + s.status + '"></span><b>' + s.id + '</b><span>' + esc(s.name) + '</span>' +
          '<em>' + esc(STATUS_LABEL[s.status] || s.status) + '</em><small>' + esc(GATE_LABEL[s.gate_status] || '未运行') + '</small></div>';
      }).join('') + '</div></section>' +
      '<section class="card"><h3>最近计时</h3><table class="data-table"><thead><tr><th>阶段</th><th>开始</th><th>时长</th><th>备注</th></tr></thead><tbody>' +
      (recent || '<tr><td colspan="4" class="empty">暂无记录</td></tr>') + '</tbody></table></section>' +
      '</div>';
    const back = document.getElementById('dash-stage');
    if (back) back.addEventListener('click', function () { location.hash = '#/stage/' + state.current_stage; });
  }).catch(showError);
}

function confirmLeave() {
  if (!S.dirty) return true;
  return window.confirm('当前文档有未保存修改，确定离开吗？');
}

/* ---------------- Stage page ---------------- */

function renderStagePage() {
  const stage = S.stage;
  const main = document.getElementById('main');
  if (!stage) { main.innerHTML = '<div class="boot">加载阶段…</div>'; return; }
  const statusPill = pill('阶段状态：' + (STATUS_LABEL[stage.status] || stage.status), stageKind(stage.status));
  const gateStatus = stage.gate && stage.gate.status ? stage.gate.status : null;
  main.innerHTML =
    '<div class="page-head"><div><h2>' + stage.stage.id + ' · ' + esc(stage.stage.name) + '</h2>' +
    '<p>' + esc(stage.stage.desc) + '</p></div><div class="btn-row">' + statusPill +
    (gateStatus ? pill('闸门：' + GATE_LABEL[gateStatus], gateStatus === 'pass' ? 'ok' : 'danger') : pill('闸门未运行', '')) + '</div></div>' +
    '<div class="stage-grid">' +
    '<section class="card"><div class="doc-list" id="doc-list">' + stage.docs.map(function (doc) {
      return '<button class="doc-item" data-path="' + esc(doc.path) + '"><span class="dot ' + (doc.exists ? (doc.locked ? 'lock' : 'ok') : '') + '"></span><span class="path">' + esc(doc.path.replace('docs/', '')) + '</span></button>';
    }).join('') + '</div></section>' +
    '<section class="card editor-card" id="editor-card"><div class="editor-head"><div class="editor-title"><strong id="doc-title">选择左侧文档</strong><span id="doc-sub">保存后会生成版本副本</span></div>' +
    '<div class="editor-tools"><button class="btn" id="btn-fields">填写区</button><button class="btn" id="btn-preview">预览</button><button class="btn primary" id="btn-save">保存</button></div></div>' +
    '<div class="fill-panel" id="fill-panel" hidden></div>' +
    '<div class="editor-body" id="editor-body"><textarea id="editor" spellcheck="false" placeholder="选择左侧文档开始编辑…"></textarea><div class="preview" id="preview"></div></div></section>' +
    '<aside class="side-col">' +
    '<div class="card side-card"><h3>章节</h3><div class="outline-tools"><button class="btn tiny" id="btn-add-section">+ 章节</button><button class="btn tiny" id="btn-add-check">+ 检查项</button></div><div id="outline" class="outline"><div class="empty">选择文档后显示层级</div></div></div>' +
    '<div class="card side-card"><h3>修改高亮</h3><div id="diff-box"><div class="empty">对比最近冻结/初始版本…</div></div></div>' +
    '<div class="card side-card"><h3>影响推理</h3><div id="insight-box"><div class="empty">检测修改后给出下游检查建议</div></div></div>' +
    '<div class="card side-card"><h3>闸门</h3><div class="gate-box" id="gate-box">' + gateHtml(stage) + '</div>' +
    '<div class="btn-row" style="margin-top:10px"><button class="btn" id="btn-gate">运行闸门</button>' +
    '<button class="btn primary" id="btn-freeze"' + (stage.status === 'frozen' ? ' disabled' : '') + '>冻结</button>' +
    '<button class="btn" id="btn-handoff"' + (stage.status === 'frozen' ? '' : ' disabled') + '>交接包</button>' +
    '<button class="btn" id="btn-next"' + (stage.status === 'frozen' ? '' : ' disabled') + '>下一步</button></div></div>' +
    '<div class="card side-card"><h3>版本</h3><div id="version-box"><div class="empty">选择文档后显示版本</div></div></div>' +
    '<div class="card side-card"><h3>本地目录</h3><div class="kv"><span>阶段</span><b>stages/' + esc(stage.folder) + '</b><span>快照</span><b>' + esc(stage.snapshot || '—') + '</b></div>' +
    '<p style="margin-top:8px">文件仍保存在项目 docs/，阶段文件夹里是可读版本和冻结快照。</p></div>' +
    '</aside></div>';

  document.querySelectorAll('[data-path]').forEach(function (button) {
    button.addEventListener('click', function () {
      if (!confirmLeave()) return;
      openArtifact(button.getAttribute('data-path'));
    });
  });
  document.getElementById('btn-save').addEventListener('click', saveArtifact);
  document.getElementById('btn-gate').addEventListener('click', runGate);
  document.getElementById('btn-freeze').addEventListener('click', freezeStage);
  document.getElementById('btn-handoff').addEventListener('click', requestHandoff);
  document.getElementById('btn-next').addEventListener('click', nextStage);
  document.getElementById('btn-preview').addEventListener('click', togglePreview);
  document.getElementById('btn-fields').addEventListener('click', toggleFillPanel);
  document.getElementById('btn-add-section').addEventListener('click', addSection);
  document.getElementById('btn-add-check').addEventListener('click', addCheckItem);
  loadStageInsight(stage.stage.id);
  const first = stage.docs.find(function (doc) { return doc.exists; }) || stage.docs[0];
  if (first) openArtifact(first.path);
}

function gateHtml(stage) {
  const gate = stage.gate || {};
  const items = (gate.report && gate.report.items) || [];
  let html = '<div class="line"><span>结果</span><b>' + esc(GATE_LABEL[gate.status] || '未运行') + '</b></div>' +
    '<div class="line"><span>最近运行</span><b>' + esc(gate.ran_at || '—') + '</b></div>' +
    '<div class="line"><span>退出码</span><b>' + esc(gate.exit_code == null ? '—' : gate.exit_code) + '</b></div>';
  if (items.length) {
    html += '<ul class="gate-items">' + items.slice(0, 30).map(function (item) {
      return '<li class="' + (item.level === 'FAIL' ? 'fail' : '') + '">' + esc(item.level + ' · ' + item.message) + '</li>';
    }).join('') + '</ul>';
  }
  return html;
}


function loadStageInsight(stageId) {
  Promise.all([
    api('/api/stage/diff?id=' + encodeURIComponent(stageId)).catch(function () { return null; }),
    api('/api/stage/insight?id=' + encodeURIComponent(stageId)).catch(function () { return null; })
  ]).then(function (result) {
    renderDiffBox(result[0]);
    renderInsightBox(result[1]);
  });
}

function renderDiffBox(diff) {
  const box = document.getElementById('diff-box');
  if (!box) return;
  if (!diff || !diff.docs || !diff.docs.length) {
    box.innerHTML = '<div class="empty">相对最近冻结/初始版本，暂无修改</div>';
    document.querySelectorAll('[data-path]').forEach(function (button) { button.classList.remove('changed'); });
    return;
  }
  const changed = {};
  diff.docs.forEach(function (doc) { changed[doc.path] = true; });
  document.querySelectorAll('[data-path]').forEach(function (button) {
    const path = button.getAttribute('data-path');
    button.classList.toggle('changed', !!changed[path]);
  });
  box.innerHTML = '<div class="line"><span>修改文档</span><b>' + diff.changed + '</b></div>' +
    '<div class="line"><span>新增行</span><b class="add">+' + diff.added + '</b></div>' +
    '<div class="line"><span>删除行</span><b class="del">-' + diff.removed + '</b></div>' +
    '<ul class="diff-list">' + diff.docs.map(function (doc) {
      return '<li><button data-diff-path="' + esc(doc.path) + '">' + esc(doc.path.replace('docs/', '')) +
        '<span><i class="add">+' + doc.added + '</i><i class="del">-' + doc.removed + '</i></span></button></li>';
    }).join('') + '</ul>';
  box.querySelectorAll('[data-diff-path]').forEach(function (button) {
    button.addEventListener('click', function () {
      const path = button.getAttribute('data-diff-path');
      const doc = diff.docs.find(function (item) { return item.path === path; });
      if (doc) openDiff(doc);
    });
  });
}

function openDiff(doc) {
  const lines = String(doc.diff || '').split('\n').map(function (line) {
    let cls = '';
    if (line.startsWith('+++') || line.startsWith('---')) cls = 'hunk';
    else if (line.startsWith('@@')) cls = 'hunk';
    else if (line.startsWith('+')) cls = 'add';
    else if (line.startsWith('-')) cls = 'del';
    return '<span class="' + cls + '">' + esc(line || ' ') + '</span>';
  }).join('\n');
  openModal('修改高亮 · ' + doc.path, '<pre class="diff-view">' + lines + '</pre>');
}

function renderInsightBox(insight) {
  const box = document.getElementById('insight-box');
  if (!box) return;
  if (!insight || !insight.suggestions || !insight.suggestions.length) {
    box.innerHTML = '<div class="empty">' + esc((insight && insight.summary) || '暂无下游影响') + '</div>';
    return;
  }
  box.innerHTML = '<p class="tag">' + esc(insight.summary) + '</p>' +
    insight.suggestions.map(function (item) {
      return '<button class="insight-item" data-target-stage="' + esc(item.stage) + '">' +
        '<strong>' + esc(item.stage) + ' · ' + esc(item.reason) + '</strong>' +
        '<span>' + esc((item.docs || []).join(' · ')) + '</span></button>';
    }).join('');
  box.querySelectorAll('[data-target-stage]').forEach(function (button) {
    button.addEventListener('click', function () {
      location.hash = '#/stage/' + button.getAttribute('data-target-stage');
    });
  });
}

function openArtifact(path) {
  S.selected = path;
  api('/api/artifact?path=' + encodeURIComponent(path)).then(function (info) {
    S.artifact = info;
    S.dirty = false;
    const editor = document.getElementById('editor');
    const preview = document.getElementById('preview');
    const title = document.getElementById('doc-title');
    const sub = document.getElementById('doc-sub');
    if (!editor) return;
    editor.value = info.content || '';
    editor.disabled = !!info.locked || !info.exists;
    const saveBtn = document.getElementById('btn-save');
    if (saveBtn) saveBtn.disabled = editor.disabled;
    title.textContent = path.replace('docs/', '');
    sub.textContent = info.locked ? '已冻结 · 需变更单' : (info.exists ? '可编辑 · 保存会生成版本' : '尚未创建');
    preview.innerHTML = mdToHtml(editor.value);
    renderFillPanel(editor.value, info.locked);
    renderOutline(editor.value);
    document.querySelectorAll('[data-path]').forEach(function (button) {
      button.classList.toggle('active', button.getAttribute('data-path') === path);
    });
    renderVersions(info.versions || []);
    editor.oninput = function () {
      S.dirty = true;
      preview.innerHTML = mdToHtml(editor.value);
      renderOutline(editor.value);
      sub.textContent = '未保存修改';
    };
  }).catch(showError);
}

function renderVersions(versions) {
  const box = document.getElementById('version-box');
  if (!box) return;
  if (!versions.length) { box.innerHTML = '<div class="empty">暂无历史版本</div>'; return; }
  box.innerHTML = '<ul class="version-list">' + versions.slice(0, 10).map(function (v) {
    return '<li><span>' + esc(v.at.replace('T', ' ') + ' · ' + (v.note || '保存')) + '</span>' +
      '<button class="btn" data-version="' + esc(v.version) + '">恢复</button></li>';
  }).join('') + '</ul>';
  document.querySelectorAll('[data-version]').forEach(function (button) {
    button.addEventListener('click', function () {
      if (!confirm('恢复这个版本？当前内容会先存为一个新版本。')) return;
      api('/api/restore', { method: 'POST', body: { path: S.selected, version: button.getAttribute('data-version') } })
        .then(function () { toast('已恢复版本'); openArtifact(S.selected); refreshStage(); })
        .catch(showError);
    });
  });
}

function saveArtifact() {
  const editor = document.getElementById('editor');
  if (!editor || editor.disabled) return;
  api('/api/save', { method: 'POST', body: {
    path: S.selected, content: editor.value,
    expected_hash: S.artifact ? S.artifact.hash : null, note: 'manual-save'
  }}).then(function (result) {
    S.dirty = false;
    toast('已保存 · 版本 ' + (result.versions ? result.versions.length : ''));
    openArtifact(S.selected);
    refreshStage();
  }).catch(showError);
}


function toggleFillPanel() {
  const panel = document.getElementById('fill-panel');
  if (!panel) return;
  S.fillOpen = !S.fillOpen;
  panel.hidden = !S.fillOpen;
  if (S.fillOpen) {
    const editor = document.getElementById('editor');
    renderFillPanel(editor ? editor.value : '', editor ? editor.disabled : true);
  }
}

function fillSectionFor(lines, lineIndex) {
  for (let i = lineIndex; i >= 0; i--) {
    const match = lines[i].match(/^##\s+(.+)$/);
    if (match) return match[1].trim();
  }
  return '文档';
}

function renderFillPanel(content, locked) {
  const panel = document.getElementById('fill-panel');
  if (!panel) return;
  panel.hidden = !S.fillOpen;
  const text = String(content || '');
  if (locked) {
    panel.innerHTML = '<div class="fill-lock">已冻结：全文只读。需要修改请走变更单。</div>';
    return;
  }
  const lines = text.replace(/\r\n/g, '\n').split('\n');
  const fields = [];
  let offset = 0;
  lines.forEach(function (line, index) {
    let pos = line.indexOf('【待填】');
    while (pos >= 0) {
      fields.push({ line: index, context: line.trim().slice(0, 90), section: fillSectionFor(lines, index), offset: offset + pos });
      pos = line.indexOf('【待填】', pos + 1);
    }
    offset += line.length + 1;
  });
  if (!fields.length) {
    panel.innerHTML = '<div class="fill-help">没有待填字段。黄色=待填；灰色章节=固定结构；可直接编辑 Markdown。</div>';
    return;
  }
  panel.innerHTML = '<div class="fill-help">黄色=待填；灰色 H2/H3=固定结构；修改后点“保存”。</div>' +
    '<div class="fill-list">' + fields.map(function (field, index) {
      return '<label class="fill-item"><span><b>#' + (index + 1) + '</b> ' + esc(field.section) + ' · 第 ' + (field.line + 1) + ' 行</span>' +
        '<small>' + esc(field.context) + '</small>' +
        '<input data-fill-index="' + index + '" placeholder="填写这里…" autocomplete="off"></label>';
    }).join('') + '</div>';
  panel.querySelectorAll('[data-fill-index]').forEach(function (input) {
    input.addEventListener('change', function () {
      const index = parseInt(input.getAttribute('data-fill-index'), 10);
      const value = input.value.trim();
      if (!value) return;
      let count = 0;
      const updated = text.replace(/【待填】/g, function (match) {
        if (count === index) { count += 1; return value; }
        count += 1;
        return match;
      });
      const editor = document.getElementById('editor');
      if (!editor) return;
      editor.value = updated;
      S.dirty = true;
      const preview = document.getElementById('preview');
      if (preview) preview.innerHTML = mdToHtml(editor.value);
      renderOutline(editor.value);
      renderFillPanel(editor.value, false);
      toast('已填入字段，保存后写入版本');
    });
  });
}
function togglePreview() {
  S.preview = !S.preview;
  const body = document.getElementById('editor-body');
  const preview = document.getElementById('preview');
  body.classList.toggle('single', !S.preview);
  preview.style.display = S.preview ? '' : 'none';
}

function handleShortcut(event) {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
    event.preventDefault();
    saveArtifact();
  }
}

function runGate() {
  if (!S.stage) return;
  toast('正在运行闸门…');
  api('/api/gate', { method: 'POST', body: { stage: S.stage.stage.id } }).then(function (gate) {
    openModal('闸门结果 · ' + GATE_LABEL[gate.status], '<div class="kv"><span>状态</span><b>' + esc(GATE_LABEL[gate.status]) + '</b><span>退出码</span><b>' + esc(gate.exit_code) + '</b><span>耗时</span><b>' + esc(gate.duration_ms) + ' ms</b></div><pre>' + esc((gate.stdout_tail || '') + '\n' + (gate.report ? JSON.stringify(gate.report, null, 2) : '')) + '</pre>');
    refreshStage();
  }).catch(showError);
}

function freezeStage() {
  if (!S.stage) return;
  if (!confirm('冻结当前阶段？会运行闸门、生成快照并锁定文档。')) return;
  api('/api/freeze', { method: 'POST', body: { stage: S.stage.stage.id } }).then(function (result) {
    toast('已冻结 · ' + result.snapshot);
    if (result.handoff) showHandoff(result.handoff);
    refreshStage();
  }).catch(showError);
}



function runDshHandoff(handoff, sessionMode) {
  const status = document.getElementById('dsh-status');
  const mode = sessionMode || 'current';
  if (status) status.textContent = '正在启动 DSH（' + mode + '）…';
  api('/api/handoff/run', { method: 'POST', body: { path: handoff.path, session: mode } }).then(function (result) {
    if (status) status.textContent = 'DSH 已启动，会话：' + (result.session || 'current') + '（见 GUI）';
    toast('DSH agent 已启动');
  }).catch(function (err) {
    if (status) status.textContent = '启动失败：' + err.message;
    showError(err);
  });
}
function requestHandoff() {
  if (!S.stage) return;
  toast('正在生成交接包…');
  api('/api/handoff?stage=' + encodeURIComponent(S.stage.stage.id)).then(function (handoff) {
    showHandoff(handoff);
  }).catch(showError);
}

function showHandoff(handoff) {
  const seeded = (handoff.seeded || []).length ? '<p class="tag">已自动更新：' + esc(handoff.seeded.join('、')) + '</p>' : '';
  openModal('交接包 · ' + esc(handoff.from) + ' → ' + esc(handoff.to),
    '<p class="tag">交接文件：' + esc(handoff.path) + '</p>' +
    seeded +
    '<p>把下面内容交给当前 agent；如果已启动 agent_bridge，它会自动读取交接文件。</p>' +
    '<textarea id="handoff-prompt" class="handoff-prompt" readonly></textarea>' +
    '<div class="btn-row"><button class="btn primary" id="btn-dsh-handoff">让 DSH 继续</button>' +
    '<button class="btn" id="btn-dsh-new">DSH 新会话</button>' +
    '<button class="btn" id="btn-copy-handoff">复制给 Agent</button>' +
    '<button class="btn" id="btn-close-handoff">关闭</button></div>' +
    '<p class="tag" id="dsh-status">DSH 会使用当前会话；需要修改可先复制。</p>' +
    '<p class="tag">agent_bridge：python scripts/agent_bridge.py watch --project . --command "..."</p>');
  const area = document.getElementById('handoff-prompt');
  if (area) area.value = handoff.prompt || '';
  const copy = document.getElementById('btn-copy-handoff');
  if (copy) copy.addEventListener('click', function () {
    const text = area ? area.value : '';
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () { toast('已复制交接包'); }).catch(function () { area.select(); });
    } else if (area) { area.select(); document.execCommand('copy'); toast('已复制交接包'); }
  });
  const run = document.getElementById('btn-dsh-handoff');
  if (run) run.addEventListener('click', function () { runDshHandoff(handoff, 'current'); });
  const runNew = document.getElementById('btn-dsh-new');
  if (runNew) runNew.addEventListener('click', function () { runDshHandoff(handoff, 'new'); });
  const close = document.getElementById('btn-close-handoff');
  if (close) close.addEventListener('click', closeModal);
}

function nextStage() {
  if (!S.stage) return;
  api('/api/next', { method: 'POST', body: { stage: S.stage.stage.id } }).then(function (result) {
    toast('进入 ' + result.current_stage);
    boot();
    location.hash = '#/stage/' + result.current_stage;
  }).catch(showError);
}

function refreshStage() {
  if (!S.stage) return;
  api('/api/stage?id=' + encodeURIComponent(S.stage.stage.id)).then(function (stage) {
    S.stage = stage;
    renderStagePage();
    if (S.selected) openArtifact(S.selected);
  }).catch(showError);
}

/* ---------------- Inbox ---------------- */

function renderInbox() {
  api('/api/state').then(function (state) {
    S.state = state;
    renderShell();
    const main = document.getElementById('main');
    const subs = state.submissions || [];
    main.innerHTML = '<div class="page-head"><div><h2>交接收件箱</h2><p>agent 的交付单在这里等你验收；通过后阶段进入待冻结。</p></div></div>' +
      '<div class="list">' + (subs.length ? subs.map(function (sub) {
        return '<div class="list-item"><h4>' + esc(sub.title) + ' <span class="tag">' + esc(sub.stage + ' · ' + sub.status) + '</span></h4>' +
          '<p>' + esc(sub.note || '') + '</p>' +
          '<div class="row"><span class="tag">' + esc(sub.at) + '</span><span class="btn-row">' +
          (sub.status === 'pending' ? '<button class="btn" data-sub="' + esc(sub.id) + '" data-accept="0">退回</button><button class="btn primary" data-sub="' + esc(sub.id) + '" data-accept="1">通过</button>' : '<span class="tag">已处理</span>') +
          '</span></div></div>';
      }).join('') : '<div class="empty">暂无交付单。agent 可用 gameconsole.py submit 提交。</div>') + '</div>';
    document.querySelectorAll('[data-sub]').forEach(function (button) {
      button.addEventListener('click', function () {
        const accepted = button.getAttribute('data-accept') === '1';
        const reason = accepted ? '' : prompt('退回原因', '请补充证据或按标准修改');
        if (!accepted && reason === null) return;
        api('/api/submission/resolve', { method: 'POST', body: { id: button.getAttribute('data-sub'), accepted: accepted, reason: reason } })
          .then(function () { toast(accepted ? '已通过' : '已退回'); renderInbox(); })
          .catch(showError);
      });
    });
  }).catch(showError);
}

/* ---------------- Wizard ---------------- */

function renderWizard() {
  S.wizard = {
    step: 1, name: '', idea: '', path: '', platform: 'Windows PC（Steam Demo），1080p 60 fps',
    scale: '小', engine: '5.8', browsePath: ''
  };
  app.innerHTML = '<header class="topbar"><div class="brand"><div class="logo">GF</div><div><h1>制作控制台</h1><div class="sub">从一句话到本地工程</div></div></div><div class="top-actions">' + pill('v0.7.4', '') +
    (S.state && S.state.project ? '<button class="btn" id="w-back-project">返回当前项目</button>' : '') + '</div></header>' +
    '<main class="main"><div class="wizard"><div class="card" style="padding:22px"><div class="steps"><span class="step active">1 想法</span><span class="step">2 工程路径</span><span class="step">3 创建</span></div>' +
    '<div id="wizard-body"></div></div></div></main>';
  renderWizardBody();
  const back = document.getElementById('w-back-project');
  if (back) back.addEventListener('click', function () {
    if (S.state && S.state.project) { location.hash = '#/stage/' + S.state.current_stage; boot(); }
  });
}

function renderWizardBody() {
  const w = S.wizard;
  const body = document.getElementById('wizard-body');
  if (!body) return;
  if (w.step === 1) {
    body.innerHTML = '<h2 style="margin-top:0">先说说你想做的游戏</h2><p class="tag">一句话也可以；控制台会生成 P0 立项书草稿，细节可以后面让 agent 补。</p>' +
      '<div class="field"><label>项目名</label><input id="w-name" value="' + esc(w.name) + '" placeholder="例如：生命之泉"></div>' +
      '<div class="field"><label>游戏想法（一句话 / 三句话）</label><textarea id="w-idea" placeholder="世界背景 + 角色 + 目标 + 结局">' + esc(w.idea) + '</textarea></div>' +
      '<div class="wizard-actions"><button class="btn primary" id="w-next">下一步 · 选择工程路径</button></div>';
    document.getElementById('w-next').addEventListener('click', function () {
      w.name = document.getElementById('w-name').value.trim();
      w.idea = document.getElementById('w-idea').value.trim();
      if (!w.name) { toast('先填项目名', true); return; }
      if (!w.idea) { toast('先写一句游戏想法', true); return; }
      w.step = 2; renderWizardBody();
    });
    return;
  }
  if (w.step === 2) {
    body.innerHTML = '<h2 style="margin-top:0">选择工程创建位置</h2><p class="tag">会在该目录创建 docs/、stages/、game/、.gameconsole/ 等本地文件。</p>' +
      '<div class="field"><label>工程目录</label><div class="path-row"><input id="w-path" value="' + esc(w.path) + '" placeholder="D:\\Games\\MyGame"><button class="btn" id="w-browse">浏览</button></div></div>' +
      '<div id="w-browser"></div>' +
      '<div class="split" style="margin-top:16px"><div class="field"><label>平台</label><input id="w-platform" value="' + esc(w.platform) + '"></div>' +
      '<div class="field"><label>规模</label><select id="w-scale"><option value="小">小 · 首作</option><option value="中">中</option><option value="大">大</option></select></div></div>' +
      '<div class="wizard-actions"><button class="btn" id="w-back">上一步</button><button class="btn primary" id="w-create">创建本地工程</button></div>';
    document.getElementById('w-scale').value = w.scale;
    document.getElementById('w-browse').addEventListener('click', function () {
      const p = document.getElementById('w-path').value.trim();
      loadBrowser(p || '');
    });
    document.getElementById('w-back').addEventListener('click', function () { w.step = 1; renderWizardBody(); });
    document.getElementById('w-create').addEventListener('click', function () {
      w.path = document.getElementById('w-path').value.trim();
      w.platform = document.getElementById('w-platform').value.trim();
      w.scale = document.getElementById('w-scale').value;
      if (!w.path) { toast('先选工程目录', true); return; }
      createProject();
    });
    loadBrowser(w.browsePath || '');
    return;
  }
}

function loadBrowser(path) {
  const box = document.getElementById('w-browser');
  if (!box) return;
  box.innerHTML = '<div class="empty">读取目录…</div>';
  api('/api/fs?path=' + encodeURIComponent(path)).then(function (data) {
    S.wizard.browsePath = data.path;
    let html = '<div class="browser">';
    if (data.path) {
      html += '<div class="row"><button data-dir="' + esc(data.parent || '') + '">← 上级</button><span class="tag">' + esc(data.path) + '</span></div>';
    }
    data.dirs.forEach(function (dir) {
      html += '<div class="row"><button data-dir="' + esc(dir.path) + '">📁 ' + esc(dir.name) + '</button><span class="tag">' + esc(dir.path) + '</span></div>';
    });
    html += '</div><div class="tag" style="margin-top:6px">点目录进入；路径可直接在上方输入。</div>';
    box.innerHTML = html;
    box.querySelectorAll('[data-dir]').forEach(function (button) {
      button.addEventListener('click', function () {
        const dir = button.getAttribute('data-dir');
        if (!dir) return;
        document.getElementById('w-path').value = dir;
        loadBrowser(dir);
      });
    });
  }).catch(function (error) { box.innerHTML = '<div class="empty">' + esc(error.message) + '</div>'; });
}

function createProject() {
  const w = S.wizard;
  toast('正在创建本地工程…');
  api('/api/project', { method: 'POST', body: {
    name: w.name, idea: w.idea, path: w.path, platform: w.platform,
    scale: w.scale, engine: w.engine, force: false
  }}).then(function (state) {
    S.state = state;
    toast('工程已创建：' + w.path);
    location.hash = '#/stage/P0';
    boot();
  }).catch(showError);
}

/* ---------------- Router / boot ---------------- */

function boot() {
  Promise.all([api('/api/state'), api('/api/time').catch(function () { return null; })]).then(function (result) {
    const state = result[0];
    S.time = result[1];
    S.state = state;
    if (state.needs_project) { renderWizard(); return; }
    if (!S.updateChecked) { S.updateChecked = true; setTimeout(autoCheckUpdate, 1800); }
    S.stage = null;
    S.artifact = null;
    S.selected = null;
    renderShell();
    route();
  }).catch(showError);
}

function route() {
  if (!S.state || S.state.needs_project) { renderWizard(); return; }
  const hash = location.hash || '#/stage/' + S.state.current_stage;
  if (hash === '#/inbox') { if (!confirmLeave()) return; renderInbox(); return; }
  if (hash === '#/new') { if (!confirmLeave()) return; renderWizard(); return; }
  if (hash === '#/dashboard') { if (!confirmLeave()) return; renderShell(); renderDashboard(); return; }
  const match = hash.match(/^#\/stage\/(P[0-7])/);
  const stageId = match ? match[1] : S.state.current_stage;
  if (!confirmLeave()) { location.hash = '#/stage/' + (S.stage ? S.stage.stage.id : stageId); return; }
  api('/api/stage?id=' + encodeURIComponent(stageId)).then(function (stage) {
    S.stage = stage;
    S.selected = null;
    S.dirty = false;
    renderShell();
    renderStagePage();
  }).catch(showError);
}

window.addEventListener('hashchange', route);
document.addEventListener('keydown', handleShortcut);
setInterval(updateTimerUI, 1000);
window.addEventListener('beforeunload', function (event) {
  if (S.dirty) { event.preventDefault(); event.returnValue = ''; }
});
boot();
