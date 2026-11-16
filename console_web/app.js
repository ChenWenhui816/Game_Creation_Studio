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
};

const STATUS_LABEL = { drafting: '草稿', review: '待验收', frozen: '已冻结', blocked: '阻塞' };
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

function pill(text, kind) {
  return '<span class="pill ' + (kind || '') + '">' + esc(text) + '</span>';
}

function stageKind(status) {
  if (status === 'frozen') return 'ok';
  if (status === 'review') return 'warn';
  if (status === 'blocked') return 'danger';
  return '';
}

/* ---------------- Markdown preview ---------------- */

function inlineMd(text) {
  let out = esc(text);
  out = out.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  out = out.replace(/\*([^*]+)\*/g, '<em>$1</em>');
  out = out.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>');
  out = out.replace(/\x60([^\x60]+)\x60/g, '<code>$1</code>');
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
      out.push('<h' + level + '>' + inlineMd(heading[2]) + '</h' + level + '>');
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
    '<button class="btn" id="btn-inbox">收件箱' + (state && state.pending_submissions ? ' ' + state.pending_submissions : '') + '</button>' +
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
  const refresh = document.getElementById('btn-refresh');
  if (refresh) refresh.addEventListener('click', function () { boot(); });
  const update = document.getElementById('btn-update');
  if (update) update.addEventListener('click', checkUpdate);
}

function checkUpdate() {
  toast('正在检查 GitHub 版本…');
  api('/api/update').then(function (info) {
    if (!info.ok) { toast('检查失败：' + (info.error || '网络不可用'), true); return; }
    const state = info.update_available ? '发现新版本' : '已是最新';
    openModal('版本检查 · ' + state,
      '<div class="kv"><span>当前</span><b>' + esc(info.current) + '</b><span>最新</span><b>' + esc(info.latest || '—') + '</b></div>' +
      '<p style="margin-top:12px">下载地址：<a href="' + esc(info.url) + '" target="_blank" rel="noreferrer">' + esc(info.url) + '</a></p>' +
      '<p class="tag">更新只提示，不自动覆盖项目文件。</p>');
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
    '<div class="editor-tools"><button class="btn" id="btn-preview">预览</button><button class="btn primary" id="btn-save">保存</button></div></div>' +
    '<div class="editor-body" id="editor-body"><textarea id="editor" spellcheck="false" placeholder="选择左侧文档开始编辑…"></textarea><div class="preview" id="preview"></div></div></section>' +
    '<aside class="side-col">' +
    '<div class="card side-card"><h3>闸门</h3><div class="gate-box" id="gate-box">' + gateHtml(stage) + '</div>' +
    '<div class="btn-row" style="margin-top:10px"><button class="btn" id="btn-gate">运行闸门</button>' +
    '<button class="btn primary" id="btn-freeze"' + (stage.status === 'frozen' ? ' disabled' : '') + '>冻结</button>' +
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
  document.getElementById('btn-next').addEventListener('click', nextStage);
  document.getElementById('btn-preview').addEventListener('click', togglePreview);
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
    document.querySelectorAll('[data-path]').forEach(function (button) {
      button.classList.toggle('active', button.getAttribute('data-path') === path);
    });
    renderVersions(info.versions || []);
    editor.oninput = function () {
      S.dirty = true;
      preview.innerHTML = mdToHtml(editor.value);
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
    refreshStage();
  }).catch(showError);
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
  app.innerHTML = '<header class="topbar"><div class="brand"><div class="logo">GF</div><div><h1>制作控制台</h1><div class="sub">从一句话到本地工程</div></div></div><div class="top-actions">' + pill('v0.4.0', '') +
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
  api('/api/state').then(function (state) {
    S.state = state;
    if (state.needs_project) { renderWizard(); return; }
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
  const match = hash.match(/^#\/stage\/(P[0-5])/);
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
window.addEventListener('beforeunload', function (event) {
  if (S.dirty) { event.preventDefault(); event.returnValue = ''; }
});
boot();
