#!/usr/bin/env python3
"""生成动态仪表盘HTML"""
import json, sys
from pathlib import Path

WORKSPACE = Path.home() / ".qclaw" / "workspace"
SKILLS_DIR = WORKSPACE / "skills" / "pipeline"
DASHBOARD_JSON = WORKSPACE / "memory" / "dashboard.json"
sys.path.insert(0, str(SKILLS_DIR))

def get_color(val, threshold_good=80, threshold_ok=60):
    if val is None: return '#666666'
    if val >= threshold_good: return '#00ff88'
    if val >= threshold_ok: return '#00d4ff'
    if val >= 40: return '#ffd700'
    return '#ff4466'

def build_html():
    # 尝试读取现有dashboard数据
    dash_data = None
    if DASHBOARD_JSON.exists():
        try:
            with open(DASHBOARD_JSON) as f:
                dash_data = json.load(f)
        except:
            pass

    gen_time = dash_data.get('generated_at', '—')[:19] if dash_data else '—'
    overall_val = dash_data.get('overall_score', {}).get('value') if dash_data else None
    overall_display = overall_val if overall_val is not None else '—'
    smooth_val = dash_data.get('smooth_score', {}).get('value') if dash_data else None
    smooth_display = f"{smooth_val}%" if smooth_val is not None else "未检测"
    radar = dash_data.get('radar_scores', {}) if dash_data else {}
    data_points = dash_data.get('overall_score', {}).get('data_points', 0) if dash_data else 0
    data_quality = dash_data.get('data_quality', {}).get('rating', '—') if dash_data else '—'
    organs = dash_data.get('organs', {}) if dash_data else {}
    gaps = dash_data.get('capability_gaps', {}).get('pending', []) if dash_data else []

    overall_color = get_color(overall_val)
    smooth_color = get_color(smooth_val)

    radar_labels = ['感知','认知','大脑','记忆','工具','主动','输出','平台']
    radar_keys = ['perception','cognition','brain','memory','tools','proactive','output','platform']
    radar_data = [radar.get(k) or 0 for k in radar_keys]

    # 器官格子
    organ_cells = []
    for name in ['眼睛','耳朵','大脑','记忆','嘴巴','工具','手脚']:
        info = organs.get(name, {})
        score = info.get('score')
        has_data = info.get('has_data', False)
        emoji = info.get('emoji', '⚪')
        if has_data and score is not None:
            sc = get_color(score)
            cell = f'''<div class="organ-cell" id="cell-{name}">
                <div class="text-3xl mb-2">{emoji}</div>
                <div class="font-bold mb-1">{name}</div>
                <div class="text-3xl font-bold" style="color:{sc}" id="score-{name}">{score}<span class="text-lg">%</span></div>
                <div class="text-xs text-gray-500 mt-1">成功率</div>
            </div>'''
        else:
            cell = f'''<div class="organ-cell" id="cell-{name}">
                <div class="text-3xl mb-2">{emoji}</div>
                <div class="font-bold mb-1">{name}</div>
                <div class="text-2xl" style="color:#666;font-style:italic">—</div>
                <div class="text-xs text-gray-500 mt-1">未检测</div>
            </div>'''
        organ_cells.append(cell)
    organs_html = '\n'.join(organ_cells)

    # 能力缺口
    priority_colors = {'高':'bg-red-900 text-red-300','中':'bg-yellow-900 text-yellow-300','低':'bg-green-900 text-green-300'}
    if gaps:
        rows = []
        for g in gaps[:8]:
            pc = priority_colors.get(g.get('priority','中'),'bg-gray-700')
            rows.append(f'''<tr>
                <td class="px-4 py-2"><span class="text-xs px-2 py-0.5 rounded {pc}">{g.get('priority','中')}</span></td>
                <td class="px-4 py-2 font-medium">{g.get('name','')}</td>
                <td class="px-4 py-2" style="color:#00d4ff">出现{g.get('count',0)}次</td>
                <td class="px-4 py-2 text-gray-500 text-xs">{g.get('last_seen','')[:10]}</td>
            </tr>''')
        gaps_html = f'''<table class="w-full text-sm"><thead><tr class="text-gray-500 text-left">
            <th class="px-4 py-2">优先级</th><th class="px-4 py-2">缺口能力</th>
            <th class="px-4 py-2">出现频次</th><th class="px-4 py-2">最近</th>
        </tr></thead><tbody>{"".join(rows)}</tbody></table>'''
    else:
        gaps_html = '<div class="text-gray-500 text-center py-4">暂无记录，用得越多数据越丰富 🎯</div>'

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🦞 小龙虾能力仪表盘 · 实时</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        :root {{ --bg: #0a0a0f; --card: #12121a; --border: #2a2a3a; --cyan: #00d4ff; }}
        * {{ font-family: system-ui, -apple-system, sans-serif; }}
        body {{ background: var(--bg); color: #e8e8f0; min-height: 100vh; }}
        .card {{ background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 20px; }}
        .organ-cell {{ background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 16px; text-align: center; transition: all 0.4s; cursor: default; }}
        .organ-cell:hover {{ border-color: var(--cyan); transform: translateY(-3px); box-shadow: 0 4px 20px rgba(0,212,255,0.1); }}
        .no-data {{ color: #555; font-style: italic; }}
        .pulse-dot {{ animation: pulse-dot 1.5s ease-in-out infinite; }}
        @keyframes pulse-dot {{ 0%,100% {{ opacity: 1; transform: scale(1); }} 50% {{ opacity: 0.5; transform: scale(0.85); }} }}
        .live-badge {{ display: inline-flex; align-items: center; gap: 6px; background: rgba(0,255,136,0.1); border: 1px solid rgba(0,255,136,0.3); color: #00ff88; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 500; }}
        .update-flash {{ animation: flash 0.6s ease; }}
        @keyframes flash {{ 0% {{ background: rgba(0,212,255,0.3); }} 100% {{ background: transparent; }} }}
        .gap-row:hover {{ background: rgba(255,255,255,0.03); }}
    </style>
</head>
<body class="p-6">
<div class="max-w-6xl mx-auto" id="main">

    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
        <div>
            <h1 class="text-2xl font-bold tracking-tight">🦞 小龙虾能力仪表盘</h1>
            <p class="text-gray-500 text-sm mt-1">数据来源：真实执行记录 · 无预设值</p>
        </div>
        <div class="flex items-center gap-4">
            <div class="live-badge" id="liveBadge">
                <span class="pulse-dot" style="width:8px;height:8px;background:#00ff88;border-radius:50%;display:inline-block"></span>
                LIVE · 每10秒刷新
            </div>
            <div class="text-xs text-gray-600" id="lastUpdate">等待数据...</div>
        </div>
    </div>

    <!-- 综合评分 -->
    <div class="card mb-6" id="overallCard">
        <div class="flex items-center gap-8">
            <div class="text-center min-w-[120px]">
                <div class="text-7xl font-black" id="overallScore" style="color:{overall_color};text-shadow: 0 0 40px currentColor">{overall_display}</div>
                <div class="text-gray-500 text-sm mt-2">综合评分</div>
            </div>
            <div class="h-28 w-px bg-gray-700"></div>
            <div class="grid grid-cols-2 gap-x-8 gap-y-3 text-sm min-w-[200px]">
                <div class="text-gray-400">丝滑等级</div><div id="smoothScore" style="color:{smooth_color}">{smooth_display}</div>
                <div class="text-gray-400">有效器官</div><div style="color:#00d4ff" id="dataPoints">{data_points}个</div>
                <div class="text-gray-400">数据质量</div><div id="dataQuality">{data_quality}</div>
                <div class="text-gray-400">待升级缺口</div><div id="gapCount" style="color:#ffd700">{len(gaps)}个</div>
            </div>
            <div class="ml-auto">
                <canvas id="radarChart" width="220" height="220"></canvas>
            </div>
        </div>
    </div>

    <!-- 器官状态 -->
    <div class="mb-6">
        <div class="flex items-center justify-between mb-4">
            <h2 class="text-lg font-bold flex items-center gap-2">🔬 器官真实数据 <span class="text-xs font-normal text-gray-500">需≥5条记录才出分数</span></h2>
            <button onclick="manualRefresh()" class="text-sm text-cyan-500 hover:text-cyan-400 transition">🔄 手动刷新</button>
        </div>
        <div class="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3" id="organsGrid">
            {organs_html}
        </div>
    </div>

    <!-- 能力缺口 -->
    <div class="card">
        <div class="flex items-center justify-between mb-4">
            <h2 class="text-lg font-bold flex items-center gap-2">⚠️ 待升级能力缺口 <span class="text-xs font-normal text-gray-500">来自真实遇到的问题</span></h2>
            <span class="text-xs text-gray-600">出现≥2次自动列入</span>
        </div>
        <div id="gapsContainer">
            {gaps_html}
        </div>
    </div>

    <!-- 数据说明 -->
    <div class="mt-6 text-center text-gray-600 text-xs">
        每10秒自动刷新 · 数据来自 task_recorder / memory_probe / reasoning_probe / gap_recorder
        · 浏览器本地轮询，不依赖服务器推送
    </div>
</div>

<script>
let radarChart = null;
let lastDataHash = '';

// ── 轮询获取最新数据 ──────────────────────────────────────────
async function fetchDashboard() {{
    try {{
        const resp = await fetch('../memory/dashboard.json?t=' + Date.now());
        if (!resp.ok) return;
        const data = await resp.json();
        const newHash = JSON.stringify(data.overall_score) + JSON.stringify(data.organs);
        if (newHash === lastDataHash) return;  // 数据没变，不更新
        lastDataHash = newHash;
        updateUI(data);
    }} catch (e) {{
        console.log('等待dashboard数据...');
    }}
}}

// ── 更新界面 ──────────────────────────────────────────────
function updateUI(data) {{
    // 更新时间戳
    const ts = data.generated_at || '—';
    document.getElementById('lastUpdate').textContent = '更新: ' + ts.slice(0, 19);

    // 综合评分
    const ov = data.overall_score;
    if (ov && ov.value !== null) {{
        const el = document.getElementById('overallScore');
        el.textContent = ov.value;
        el.style.color = getColor(ov.value);
        el.style.textShadow = '0 0 40px ' + getColor(ov.value);
        el.classList.add('update-flash');
        setTimeout(() => el.classList.remove('update-flash'), 600);
    }}

    // 丝滑
    const sv = data.smooth_score;
    if (sv) {{
        const el = document.getElementById('smoothScore');
        el.textContent = sv.display;
        el.style.color = getColor(sv.value);
    }}

    // 数据点数
    if (data.overall_score) {{
        document.getElementById('dataPoints').textContent = (data.overall_score.data_points || 0) + '个';
        document.getElementById('dataQuality').textContent = data.data_quality ? data.data_quality.rating : '—';
    }}

    // 缺口数
    const gaps = data.capability_gaps ? data.capability_gaps.pending : [];
    document.getElementById('gapCount').textContent = gaps.length + '个';

    // 器官格子
    const organs = data.organs || {{}};
    const organNames = ['眼睛','耳朵','大脑','记忆','嘴巴','工具','手脚'];
    organNames.forEach(name => {{
        const info = organs[name] || {{}};
        const score = info.score;
        const hasData = info.has_data;
        const cellId = 'cell-' + name;
        const cell = document.getElementById(cellId);
        if (!cell) return;

        if (hasData && score !== null && score !== undefined) {{
            const sc = getColor(score);
            const scoreEl = cell.querySelector('[id^="score-"]') || cell.children[2];
            if (scoreEl) {{
                scoreEl.innerHTML = score + '<span class="text-lg">%</span>';
                scoreEl.style.color = sc;
            }}
            cell.classList.add('update-flash');
            setTimeout(() => cell.classList.remove('update-flash'), 600);
        }}
    }});

    // 能力缺口
    const gapsContainer = document.getElementById('gapsContainer');
    if (gaps.length > 0) {{
        const priorityColors = {{'高':'bg-red-900 text-red-300','中':'bg-yellow-900 text-yellow-300','低':'bg-green-900 text-green-300'}};
        let rows = '';
        gaps.slice(0, 8).forEach(g => {{
            const pc = priorityColors[g.priority] || 'bg-gray-700';
            rows += '<tr class="gap-row">' +
                '<td class="px-4 py-2"><span class="text-xs px-2 py-0.5 rounded ' + pc + '">' + (g.priority||'中') + '</span></td>' +
                '<td class="px-4 py-2 font-medium">' + (g.name||'') + '</td>' +
                '<td class="px-4 py-2" style="color:#00d4ff">出现' + (g.count||0) + '次</td>' +
                '<td class="px-4 py-2 text-gray-500 text-xs">' + ((g.last_seen||'')[:10]) + '</td></tr>';
        }});
        gapsContainer.innerHTML = '<table class="w-full text-sm"><thead><tr class="text-gray-500 text-left">' +
            '<th class="px-4 py-2">优先级</th><th class="px-4 py-2">缺口能力</th><th class="px-4 py-2">出现频次</th><th class="px-4 py-2">最近</th>' +
            '</tr></thead><tbody>' + rows + '</tbody></table>';
    }}

    // 雷达图
    updateRadar(data.radar_scores || {{}});
}}

function getColor(val) {{
    if (val === null || val === undefined) return '#666';
    if (val >= 80) return '#00ff88';
    if (val >= 60) return '#00d4ff';
    if (val >= 40) return '#ffd700';
    return '#ff4466';
}}

// ── 雷达图 ─────────────────────────────────────────────────
function updateRadar(radar) {{
    const labels = ['感知','认知','大脑','记忆','工具','主动','输出','平台'];
    const keys = ['perception','cognition','brain','memory','tools','proactive','output','platform'];
    const data = keys.map(k => radar[k] || 0);

    const ctx = document.getElementById('radarChart');
    if (!ctx) return;

    if (!radarChart) {{
        radarChart = new Chart(ctx, {{
            type: 'radar',
            data: {{
                labels: labels,
                datasets: [{{
                    label: '能力',
                    data: data,
                    backgroundColor: 'rgba(0,212,255,0.12)',
                    borderColor: '#00d4ff',
                    borderWidth: 2,
                    pointBackgroundColor: '#00d4ff',
                    pointRadius: 4
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: true,
                scales: {{
                    r: {{
                        beginAtZero: true,
                        max: 10,
                        ticks: {{ stepSize: 2, color: '#555', backdropColor: 'transparent', font: {{size:10}} }},
                        grid: {{ color: 'rgba(255,255,255,0.08)' }},
                        angleLines: {{ color: 'rgba(255,255,255,0.08)' }},
                        pointLabels: {{ color: '#888', font: {{size:11}} }}
                    }}
                }},
                plugins: {{ legend: {{ display: false }} }}
            }}
        }});
    }} else {{
        radarChart.data.datasets[0].data = data;
        radarChart.update('none');
    }}
}}

// ── 手动刷新：重新生成数据 ─────────────────────────────────
async function manualRefresh() {{
    // 先触发Python生成最新JSON
    try {{
        await fetch('pipeline/dashboard_generator.py?force=1', {{ mode: 'no-cors' }}).catch(() => {{}});
    }} catch(e) {{}}
    // 然后重新获取
    await fetchDashboard();
}}

// ── 启动 ──────────────────────────────────────────────────
fetchDashboard();  // 立即执行一次
setInterval(fetchDashboard, 10000);  // 每10秒轮询
</script>
</body>
</html>'''

with open(SKILLS_DIR / 'real_capability_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(build_html())
print(f'✅ 动态仪表盘已生成')

if __name__ == '__main__':
    build_html()
