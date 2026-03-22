"""
dashboard_generator.py — 真实数据仪表盘生成器
读取四个探针的真实数据，生成仪表盘 JSON

所有数字来自真实执行记录，没有预设值。
没有足够数据的器官显示「未检测」。

用法：
  from dashboard_generator import generate_dashboard, get_dashboard_data

  # 生成并保存仪表盘
  dashboard = generate_dashboard()

  # 获取数据（不保存）
  data = get_dashboard_data()
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

WORKSPACE = Path.home() / ".qclaw" / "workspace"
SKILLS_DIR = WORKSPACE / "skills" / "pipeline"
OUTPUT_FILE = WORKSPACE / "memory" / "dashboard.json"

# 添加 pipeline 路径
sys.path.insert(0, str(SKILLS_DIR))


def get_dashboard_data() -> Dict[str, Any]:
    """
    从四个探针收集真实数据，生成仪表盘
    """
    # 延迟导入避免循环依赖
    from task_recorder import get_organ_score, get_smooth_score, get_organ_stats, get_task_summary
    from memory_probe import get_memory_stats, get_memory_hit_rate
    from reasoning_probe import get_brain_score, get_reasoning_quality
    from gap_recorder import get_pending_upgrades, get_gap_stats

    # ─── 各器官真实数据 ─────────────────────────────────
    
    organ_mapping = {
        "眼睛": "eyes",
        "耳朵": "ears", 
        "大脑": "brain",
        "记忆": "memory",
        "嘴巴": "mouth",
        "工具": "tools",
        "手脚": "hands"
    }

    organs = {}
    
    # 任务执行记录（眼睛、工具等）
    organ_scores = get_organ_score_all()
    for organ_name, score in organ_scores.items():
        organs[organ_name] = {
            "score": score,
            "has_data": score is not None,
            "display": score if score is not None else "未检测",
            "emoji": _get_organ_emoji(organ_name)
        }
    
    # 记忆专项
    memory_hit_rate = get_memory_hit_rate()
    if "记忆" in organs:
        organs["记忆"]["score"] = memory_hit_rate
        organs["记忆"]["has_data"] = memory_hit_rate is not None
        organs["记忆"]["display"] = memory_hit_rate if memory_hit_rate is not None else "未检测"
        organs["记忆"]["source"] = "mem0ai检索命中率"
    
    # 大脑专项（推理采纳率）
    brain_score = get_brain_score()
    if "大脑" in organs:
        organs["大脑"]["score"] = brain_score
        organs["大脑"]["has_data"] = brain_score is not None
        organs["大脑"]["display"] = brain_score if brain_score is not None else "未检测"
        organs["大脑"]["source"] = "推理采纳率"

    # 丝滑等级
    smooth_score = get_smooth_score()
    
    # 综合评分（只有有数据的器官才能参与）
    scores_with_data = [v["score"] for v in organs.values() if v["has_data"] and isinstance(v["score"], (int, float))]
    if smooth_score is not None:
        scores_with_data.append(smooth_score)
    
    if scores_with_data:
        overall = round(sum(scores_with_data) / len(scores_with_data))
    else:
        overall = None

    # ─── 任务汇总 ─────────────────────────────────────
    task_summary = get_task_summary()
    
    # ─── 能力缺口（真实记录）──
    pending_gaps = get_pending_upgrades()
    gap_stats = get_gap_stats()
    
    # ─── 组装仪表盘数据 ─────────────────────────────────
    
    dashboard = {
        "generated_at": datetime.now().isoformat(),
        "data_source": "真实执行记录",
        "version": "2.0",
        
        # 综合评分
        "overall_score": {
            "value": overall,
            "display": overall if overall is not None else "数据不足",
            "has_data": overall is not None,
            "data_points": len(scores_with_data)
        },
        
        # 丝滑等级
        "smooth_score": {
            "value": smooth_score,
            "display": f"{smooth_score}%" if smooth_score is not None else "未检测",
            "has_data": smooth_score is not None,
            "description": "任务完成未打断用户的比率"
        },
        
        # 各器官数据
        "organs": organs,
        
        # 器官汇总
        "organ_summary": {
            "total": len(organs),
            "with_data": sum(1 for v in organs.values() if v["has_data"]),
            "without_data": sum(1 for v in organs.values() if not v["has_data"]),
            "best": _get_best_organ(organs),
            "weakest": _get_weakest_organ(organs)
        },
        
        # 任务统计
        "task_stats": task_summary,
        
        # 能力缺口
        "capability_gaps": {
            "pending": pending_gaps,
            "stats": gap_stats
        },
        
        # 数据质量
        "data_quality": {
            "organ_data_points": sum(1 for v in organs.values() if v["has_data"]),
            "total_data_points": len(scores_with_data),
            "rating": "优秀" if len(scores_with_data) >= 6 else "良好" if len(scores_with_data) >= 3 else "数据积累中"
        },
        
        # 雷达图用的分类分数
        "radar_scores": _compute_radar_scores(organs)
    }
    
    return dashboard


def get_organ_score_all() -> Dict[str, Optional[int]]:
    """获取所有器官的执行成功率"""
    from task_recorder import get_organ_stats
    
    stats = get_organ_stats()
    result = {}
    
    for organ in ["眼睛", "耳朵", "大脑", "记忆", "嘴巴", "工具", "手脚"]:
        if organ in stats:
            s = stats[organ]
            if s["total"] >= 5:
                result[organ] = round(s["success"] / s["total"] * 100)
            else:
                result[organ] = None  # 数据不足
        else:
            result[organ] = None
    
    return result


def _get_organ_emoji(organ: str) -> str:
    emoji_map = {
        "眼睛": "👁️",
        "耳朵": "👂",
        "大脑": "🧠",
        "记忆": "💾",
        "嘴巴": "🗣️",
        "工具": "🔧",
        "手脚": "🦶"
    }
    return emoji_map.get(organ, "⚪")


def _get_best_organ(organs: Dict) -> Optional[Dict]:
    """找出分数最高的器官"""
    with_data = [(k, v) for k, v in organs.items() if v["has_data"]]
    if not with_data:
        return None
    best = max(with_data, key=lambda x: x[1]["score"])
    return {"organ": best[0], "score": best[1]["score"], "emoji": best[1]["emoji"]}


def _get_weakest_organ(organs: Dict) -> Optional[Dict]:
    """找出分数最低的器官"""
    with_data = [(k, v) for k, v in organs.items() if v["has_data"]]
    if not with_data:
        return None
    weakest = min(with_data, key=lambda x: x[1]["score"])
    return {"organ": weakest[0], "score": weakest[1]["score"], "emoji": weakest[1]["emoji"]}


def _compute_radar_scores(organs: Dict) -> Dict[str, float]:
    """
    将器官数据映射到雷达图维度
    感知/认知/大脑/记忆/工具/主动/输出/平台
    """
    # 眼睛 → 感知
    # 耳朵 → 认知  
    # 大脑 → 大脑
    # 记忆 → 记忆
    # 工具 → 工具
    # 嘴巴 → 输出
    # 手脚 → 平台(执行)
    
    result = {
        "perception": None,
        "cognition": None,
        "brain": None,
        "memory": None,
        "tools": None,
        "proactive": None,
        "output": None,
        "platform": None
    }
    
    for k, v in organs.items():
        score = v.get("score") if isinstance(v, dict) else None
        if score is None:
            continue
        if k == "眼睛":
            result["perception"] = round(score / 10, 1)
        elif k == "耳朵":
            result["cognition"] = round(score / 10, 1)
        elif k == "大脑":
            result["brain"] = round(score / 10, 1)
        elif k == "记忆":
            result["memory"] = round(score / 10, 1)
        elif k == "工具":
            result["tools"] = round(score / 10, 1)
        elif k == "嘴巴":
            result["output"] = round(score / 10, 1)
        elif k == "手脚":
            result["platform"] = round(score / 10, 1)
    
    return result


def generate_dashboard(write_html: bool = True) -> Dict[str, Any]:
    """
    生成仪表盘数据，写入 dashboard.json
    可选生成 HTML 可视化
    """
    dashboard = get_dashboard_data()
    
    # 保存 JSON
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(dashboard, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 仪表盘已更新 ({dashboard['generated_at']})")
    print(f"   综合评分: {dashboard['overall_score']['display']}")
    print(f"   丝滑等级: {dashboard['smooth_score']['display']}")
    print(f"   器官有数据: {dashboard['organ_summary']['with_data']}/{dashboard['organ_summary']['total']}")
    print(f"   待升级缺口: {len(dashboard['capability_gaps']['pending'])}个")
    
    # 生成 HTML（直接覆盖）
    if write_html:
        try:
            generate_html_dashboard(dashboard)
        except Exception as e:
            print(f"⚠️ HTML生成失败: {e}")
    
    return dashboard


def generate_html_dashboard(dashboard: Dict):
    """生成可视化 HTML 仪表盘"""
    from pathlib import Path
    
    html_path = SKILLS_DIR / "real_capability_dashboard.html"
    
    organs_html = _render_organs_html(dashboard.get("organs", {}))
    gaps_html = _render_gaps_html(dashboard.get("capability_gaps", {}).get("pending", []))
    
    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🦞 真实能力仪表盘</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        :root {{
            --bg: #0a0a0f;
            --card: #12121a;
            --border: #2a2a3a;
            --cyan: #00d4ff;
            --green: #00ff88;
            --yellow: #ffd700;
            --red: #ff4466;
            --purple: #a855f7;
        }}
        body {{ background: var(--bg); color: #e8e8f0; font-family: system-ui, sans-serif; }}
        .card {{ background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 20px; }}
        .organ-cell {{ background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 16px; text-align: center; transition: all 0.3s; }}
        .organ-cell:hover {{ border-color: var(--cyan); transform: translateY(-2px); }}
        .no-data {{ color: #666; font-style: italic; }}
        .score-great {{ color: var(--green); }}
        .score-ok {{ color: var(--cyan); }}
        .score-warn {{ color: var(--yellow); }}
        .score-bad {{ color: var(--red); }}
        .pulse {{ animation: pulse 2s infinite; }}
        @keyframes pulse {{ 0%,100% {{ opacity: 1; }} 50% {{ opacity: 0.5; }} }}
    </style>
</head>
<body class="p-6">
    <div class="max-w-6xl mx-auto">
        <!-- Header -->
        <div class="flex justify-between items-center mb-6">
            <div>
                <h1 class="text-2xl font-bold">🦞 真实能力仪表盘 <span class="text-xs text-gray-500">v2.0 数据驱动</span></h1>
                <p class="text-gray-500 text-sm">数据来源：{dashboard["data_source"]} · 生成时间：{dashboard["generated_at"][:19]}</p>
            </div>
            <button onclick="refresh()" class="px-4 py-2 bg-cyan-600 hover:bg-cyan-700 rounded-lg text-sm">🔄 刷新</button>
        </div>

        <!-- 综合评分 -->
        <div class="card mb-6">
            <div class="flex items-center gap-8">
                <div class="text-center">
                    <div class="text-6xl font-bold {'score-great' if (dashboard.get('overall_score',{{}}).get('value') or 0) >= 80 else 'score-ok' if (dashboard.get('overall_score',{{}}).get('value') or 0) >= 60 else 'score-warn'}" style="text-shadow: 0 0 30px currentColor">
                        {dashboard.get('overall_score', {}).get('display', '—')}
                    </div>
                    <div class="text-gray-500 text-sm mt-1">综合评分</div>
                </div>
                <div class="h-24 w-px bg-gray-700"></div>
                <div class="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
                    <div class="text-gray-400">丝滑等级</div>
                    <div class="{'score-great' if (dashboard.get('smooth_score',{{}}).get('value') or 0) >= 80 else 'score-ok' if (dashboard.get('smooth_score',{{}}).get('value') or 0) >= 60 else 'score-warn'}">{dashboard.get('smooth_score', {}).get('display', '未检测')}</div>
                    <div class="text-gray-400">有效数据点</div>
                    <div class="cyan-400">{dashboard.get('overall_score', {}).get('data_points', 0)}个器官</div>
                    <div class="text-gray-400">数据质量</div>
                    <div>{dashboard.get('data_quality', {}).get('rating', '—')}</div>
                    <div class="text-gray-400">待升级缺口</div>
                    <div class="{'score-warn' if dashboard.get('capability_gaps',{{}}).get('pending') else 'score-great'}">{len(dashboard.get('capability_gaps', {{}}).get('pending', []))}个</div>
                </div>
                <div class="ml-auto">
                    <canvas id="radarCanvas" width="200" height="200"></canvas>
                </div>
            </div>
        </div>

        <!-- 器官状态 -->
        <div class="mb-6">
            <h2 class="text-lg font-bold mb-4">🔬 真实数据（来源：任务执行记录）</h2>
            <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
                {organs_html}
            </div>
        </div>

        <!-- 能力缺口 -->
        <div class="card">
            <h2 class="text-lg font-bold mb-4">⚠️ 待升级能力缺口（来源：实际遇到）</h2>
            {gaps_html if gaps_html else '<div class="text-gray-500 text-center py-4">暂无记录，继续积累数据中...</div>'}
        </div>

        <!-- Footer -->
        <div class="text-center text-gray-600 text-xs mt-6">
            数据来自最近500条任务记录 | 命中率<5条显示「未检测」
        </div>
    </div>

    <script>
        function refresh() {{ location.reload(); }}

        // 雷达图
        const radarScores = {json.dumps(dashboard.get('radar_scores', {}), ensure_ascii=False)};
        const labels = ['感知', '认知', '大脑', '记忆', '工具', '主动', '输出', '平台'];
        const data = [
            radarScores['perception'],
            radarScores['cognition'],
            radarScores['brain'],
            radarScores['memory'],
            radarScores['tools'],
            radarScores['proactive'],
            radarScores['output'],
            radarScores['platform']
        ];

        const ctx = document.getElementById('radarCanvas');
        if (ctx) {{
            new Chart(ctx, {{
                type: 'radar',
                data: {{
                    labels: labels,
                    datasets: [{{
                        data: data.map(v => v || 0),
                        backgroundColor: 'rgba(0,212,255,0.1)',
                        borderColor: '#00d4ff',
                        borderWidth: 2
                    }}]
                }},
                options: {{
                    responsive: true,
                    scales: {{ r: {{ beginAtZero: true, max: 10 }} }},
                    plugins: {{ legend: {{ display: false }} }}
                }}
            }});
        }}
    </script>
</body>
</html>'''
    
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"   HTML: {html_path}")


def _render_organs_html(organs: Dict) -> str:
    """渲染器官单元格"""
    html_parts = []
    
    for organ_name in ["眼睛", "耳朵", "大脑", "记忆", "嘴巴", "工具", "手脚"]:
        info = organs.get(organ_name, {})
        score = info.get("score")
        has_data = info.get("has_data", False)
        emoji = info.get("emoji", "⚪")
        
        if has_data and score is not None:
            if score >= 80:
                score_class = "score-great"
            elif score >= 60:
                score_class = "score-ok"
            elif score >= 40:
                score_class = "score-warn"
            else:
                score_class = "score-bad"
            
            score_html = f'<div class="text-3xl font-bold {score_class}">{score}<span class="text-lg">%</span></div>'
        else:
            score_html = '<div class="text-2xl no-data">—</div>'
        
        html_parts.append(f'''
        <div class="organ-cell">
            <div class="text-3xl mb-2">{emoji}</div>
            <div class="font-bold mb-1">{organ_name}</div>
            {score_html}
            <div class="text-xs text-gray-500 mt-1">{"成功率" if has_data else "未检测"}</div>
        </div>
        ''')
    
    return ''.join(html_parts)


def _render_gaps_html(pending: List) -> str:
    """渲染能力缺口列表"""
    if not pending:
        return ""
    
    priority_colors = {
        "高": "bg-red-900 text-red-300",
        "中": "bg-yellow-900 text-yellow-300",
        "低": "bg-green-900 text-green-300"
    }
    
    rows = []
    for gap in pending[:10]:
        color = priority_colors.get(gap.get("priority", "中"), "bg-gray-700")
        rows.append(f'''
        <tr>
            <td class="px-4 py-2"><span class="text-xs px-2 py-0.5 rounded {color}">{gap.get('priority', '中')}</span></td>
            <td class="px-4 py-2 font-medium">{gap.get('name', '')}</td>
            <td class="px-4 py-2 text-cyan-400">出现{gap.get('count', 0)}次</td>
            <td class="px-4 py-2 text-gray-500 text-xs">{gap.get('last_seen', '')[:10]}</td>
        </tr>
        ''')
    
    return f'''
    <table class="w-full text-sm">
        <thead>
            <tr class="text-gray-500 text-left">
                <th class="px-4 py-2">优先级</th>
                <th class="px-4 py-2">缺口能力</th>
                <th class="px-4 py-2">出现频次</th>
                <th class="px-4 py-2">最近</th>
            </tr>
        </thead>
        <tbody>
            {"".join(rows)}
        </tbody>
    </table>
    '''


if __name__ == "__main__":
    print("🔬 生成真实数据仪表盘...\n")
    dashboard = generate_dashboard()
    print(f"\n📊 数据预览：")
    print(f"  综合评分: {dashboard['overall_score']['display']}")
    print(f"  器官有数据: {dashboard['organ_summary']['with_data']}/{dashboard['organ_summary']['total']}")
    if dashboard.get('organ_summary').get('weakest'):
        w = dashboard['organ_summary']['weakest']
        print(f"  最弱器官: {w['emoji']}{w['organ']} ({w['score']}%)")
