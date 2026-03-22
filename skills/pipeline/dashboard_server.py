#!/usr/bin/env python3
"""
dashboard_server.py — 小龙虾能力仪表盘 v3
http://localhost:8765
"""
import http.server, socketserver, json, os, sys
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse

WORKSPACE = Path.home() / ".qclaw" / "workspace"
SKILLS_DIR = WORKSPACE / "skills" / "pipeline"
PORT = 8765
sys.path.insert(0, str(SKILLS_DIR))

PERSONAS = {
    "情报专家":   {"emoji":"🕵️","color":"#a855f7","desc":"发现信号、追踪情报","weights":{"眼睛":0.30,"耳朵":0.25,"大脑":0.20,"记忆":0.15,"工具":0.10}},
    "代码工程师": {"emoji":"👨‍💻","color":"#06b6d4","desc":"写代码、修Bug、搭系统","weights":{"工具":0.35,"眼睛":0.20,"大脑":0.25,"记忆":0.10,"手脚":0.10}},
    "产品经理":   {"emoji":"📋","color":"#f59e0b","desc":"理解需求、排优先级","weights":{"大脑":0.30,"嘴巴":0.20,"工具":0.20,"记忆":0.15,"耳朵":0.15}},
    "架构师":     {"emoji":"🏗️","color":"#ef4444","desc":"设计系统、预判风险","weights":{"大脑":0.40,"记忆":0.20,"工具":0.15,"眼睛":0.15,"耳朵":0.10}},
    "生物科学家": {"emoji":"🧬","color":"#10b981","desc":"研究、分析、验证","weights":{"记忆":0.30,"眼睛":0.25,"大脑":0.25,"耳朵":0.10,"工具":0.10}},
}
ORGS = ["眼睛","耳朵","大脑","记忆","嘴巴","工具","手脚"]
ORG_EMOJI = {"眼睛":"👁️","耳朵":"👂","大脑":"🧠","记忆":"💾","嘴巴":"🗣️","工具":"🔧","手脚":"🦶"}

def _c(v,tg=80,to=60):
    if v is None: return "#555"
    if v>=tg: return "#00ff88"
    if v>=to: return "#00d4ff"
    if v>=40: return "#ffd700"
    return "#ff4466"

def _sl(v):
    if v is None: return "—"
    return "卓越" if v>=90 else "优秀" if v>=80 else "良好" if v>=70 else "一般" if v>=60 else "需提升"

def collect():
    from task_recorder import get_organ_stats,get_smooth_score,get_task_summary
    from task_recorder import get_seamless_detail,get_seamless_score,get_stability_score
    from memory_probe import get_memory_stats
    from reasoning_probe import get_reasoning_quality
    from gap_recorder import get_pending_upgrades

    stats = get_organ_stats()
    organs = {}
    for n in ORGS:
        s = stats.get(n,{"total":0,"success":0,"interrupted":0})
        hd = s["total"]>=5
        sc = round(s["success"]/s["total"]*100) if hd else None
        organs[n]={"score":sc,"has_data":hd,"total":s["total"],"success":s["success"],"failed":s["total"]-s["success"],"interrupted":s["interrupted"],"emoji":ORG_EMOJI.get(n,"⚪")}

    smooth = get_smooth_score()
    seam_detail = get_seamless_detail()
    seam = get_seamless_score()
    stability = get_stability_score()
    rq = get_reasoning_quality()
    brain = rq.get("brain_score")
    mem = get_memory_stats()
    mem_hit = mem.get("hit_rate")
    gaps = get_pending_upgrades()

    sc_list = []
    for info in organs.values():
        if info["has_data"] and info["score"] is not None: sc_list.append(info["score"])
    if brain is not None: sc_list.append(brain)
    if smooth is not None: sc_list.append(smooth)
    if stability is not None: sc_list.append(stability)
    if seam is not None: sc_list.append(seam)
    overall = round(sum(sc_list)/len(sc_list)) if sc_list else None

    radar = {
        "perception": round(organs.get("眼睛",{}).get("score") or 0)/10,
        "cognition": round(organs.get("耳朵",{}).get("score") or 0)/10,
        "brain": round(brain or 0)/10,
        "memory": round(mem_hit or 0)/10,
        "tools": round(organs.get("工具",{}).get("score") or 0)/10,
        "proactive": None,
        "output": round(organs.get("嘴巴",{}).get("score") or 0)/10,
        "platform": round(organs.get("手脚",{}).get("score") or 0)/10,
    }

    personas = _personas(organs, brain, mem_hit)
    return {
        "generated_at": datetime.now().isoformat(),
        "overall_score": overall,
        "smooth_score": smooth,
        "seamless_score": seam,
        "seamless_detail": seam_detail,
        "stability_score": stability,
        "brain_score": brain,
        "memory_hit_rate": mem_hit,
        "organs": organs,
        "radar": radar,
        "gaps": gaps,
        "personas": personas,
        "data_points": len(sc_list),
    }

def _personas(organs, brain, mem_hit):
    results = {}
    for pid, pdef in PERSONAS.items():
        wt = sum(pdef["weights"].values())
        ws, wsum = 0, 0.0
        reasons = []
        for on, w in pdef["weights"].items():
            src = brain if on=="大脑" else mem_hit if on=="记忆" else organs.get(on,{}).get("score")
            if src is not None:
                ws += w; wsum += src*w
                reasons.append(on+str(int(src*w))+"分")
            else:
                tot = organs.get(on,{}).get("total",0)
                if tot>0:
                    ws += w*0.5; wsum += 60*w*0.5
        if ws>0:
            cov = ws/wt
            score = round((wsum/ws)*cov)
        else:
            score = None
        results[pid]={"emoji":pdef["emoji"],"color":pdef["color"],"desc":pdef["desc"],
                       "score":score,"reasons":reasons,"has_data":ws>0,"data_coverage":round(ws/wt*100) if ws>0 else 0}
    ranking = sorted([(k,v) for k,v in results.items() if v["has_data"] and v["score"] is not None], key=lambda x:-x[1]["score"])
    return {"scores":results,"ranking":[{"id":k,**v} for k,v in ranking]}

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,directory=str(WORKSPACE),**kwargs)

    def do_GET(self):
        p = urlparse(self.path)
        if p.path in ("/","/dashboard"):
            self._html()
        elif p.path=="/api/dashboard":
            self._api()
        elif p.path=="/api/status":
            self._status()
        else:
            super().do_GET()

    def _html(self):
        body = _build_html(collect())
        self.send_response(200)
        self.send_header("Content-type","text/html; charset=utf-8")
        self.send_header("Cache-Control","no-cache")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def _api(self):
        data = collect()
        self.send_response(200)
        self.send_header("Content-type","application/json; charset=utf-8")
        self.send_header("Cache-Control","no-cache")
        self.send_header("Access-Control-Allow-Origin","*")
        self.end_headers()
        self.wfile.write(json.dumps(data,ensure_ascii=False).encode("utf-8"))

    def _status(self):
        from task_recorder import get_organ_stats
        s = get_organ_stats()
        body = json.dumps({"ok":True,"total":sum(x["total"] for x in s.values()),"pid":os.getpid()})
        self.send_response(200)
        self.send_header("Content-type","application/json")
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self,*args): pass

def _tag(name, content, **attrs):
    a = " ".join(f'{k}="{v}"' for k,v in attrs.items())
    return f"<{name} {a}>{content}</{name}>"

def _build_html(d):
    orgs = d["organs"]
    gaps = d["gaps"]
    personas = d["personas"]
    overall = d["overall_score"]
    smooth = d["smooth_score"]
    seam = d["seamless_score"]
    stability = d["stability_score"]
    brain = d["brain_score"]
    mem_hit = d["memory_hit_rate"]
    radar = d["radar"]
    ts = d["generated_at"][:19]

    # organ cells
    org_cells = []
    for n in ORGS:
        info = orgs.get(n,{})
        sc = info.get("score"); hd = info.get("has_data"); tot = info.get("total",0); intr = info.get("interrupted",0)
        if hd and sc is not None:
            c = _c(sc); lbl = _sl(sc)
            intr_str = f" | 打断{intr}次" if intr > 0 else ""
            cell = f'''<div class="organ-cell" id="cell-{n}"><div class="text-3xl mb-1">{info.get("emoji","⚪")}</div><div class="font-bold mb-1">{n}</div><div class="text-3xl font-black" id="score-{n}" style="color:{c}">{sc}<span class="text-base">%</span></div><div class="text-xs mt-1" style="color:{c}">{lbl}</div><div class="text-xs text-gray-600 mt-1">{tot}次{intr_str}</div></div>'''
        else:
            need = max(0,5-tot)
            cell = f'''<div class="organ-cell" id="cell-{n}"><div class="text-3xl mb-1">{info.get("emoji","⚪")}</div><div class="font-bold mb-1">{n}</div><div class="text-2xl" style="color:#444;font-style:italic">—</div><div class="text-xs mt-1" style="color:#444">差{need}次</div></div>'''
        org_cells.append(cell)
    org_html = "".join(org_cells)

    # new metrics
    ov_d = str(overall) if overall is not None else "—"
    sm_d = str(smooth)+"%" if smooth is not None else "—"
    ss_d = str(seam)+"%" if seam is not None else "未检测"
    st_d = str(stability)+"%" if stability is not None else "未检测"
    ov_c = _c(overall); sm_c = _c(smooth); ss_c = _c(seam); st_c = _c(stability)
    bv_c = _c(brain); mv_c = _c(mem_hit)

    # seamless detail
    sd = d.get("seamless_detail") or {}
    trans = sd.get("transitions",[])
    if trans:
        trows = "".join(f'<div style="display:flex;justify-content:space-between;padding:2px 0"><span style="color:#777;font-size:13px">{t["transition"]}</span><span style="color:{_c(t["rate"])};font-size:13px">{t["success"]}/{t["total"]}={t["rate"]}%</span></div>' for t in trans[:6])
    else:
        trows = '<div style="text-align:center;color:#555;font-size:12px;padding:12px">暂无跨器官协作记录</div>'
    seam_detail_html = trows

    # gaps
    pc = {"高":"bg-red-900 text-red-300","中":"bg-yellow-900 text-yellow-300","低":"bg-green-900 text-green-300"}
    high = [g for g in gaps if str(g.get("priority","")).lower() in ["高","high"]]
    other = [g for g in gaps if str(g.get("priority","")).lower() not in ["高","high"]]
    def grow(g):
        if not g: return '<tr><td colspan="4" style="text-align:center;color:#555;padding:12px;font-size:13px">暂无</td></tr>'
        return "".join(f'<tr style="transition:background 0.2s" onmouseover="this.style.background=\'rgba(255,255,255,0.03)\'" onmouseout="this.style.background=\'\'"><td style="padding:8px"><span style="font-size:11px;padding:2px 8px;border-radius:4px;background:{pc.get(g.get("priority","中"),"#333")}">{g.get("priority","中")}</span></td><td style="padding:8px;font-size:13px">{g.get("name","")}</td><td style="padding:8px;color:#00d4ff;font-size:12px">×{g.get("count",0)}</td><td style="padding:8px;color:#666;font-size:11px">{g.get("last_seen","")[:10]}</td></tr>' for g in g[:8])
    gaps_html = f'<table style="width:100%;border-collapse:collapse"><thead><tr style="text-align:left;font-size:11px;color:#555"><th style="padding:6px 8px">级别</th><th style="padding:6px 8px">缺口能力</th><th style="padding:6px 8px">次数</th><th style="padding:6px 8px">最近</th></tr></thead><tbody>{grow(high)}{grow(other)}</tbody></table>'

    # personas
    p_cards = []
    for i, entry in enumerate(personas.get("ranking",[])[:5]):
        pid = entry["id"]; pdef = PERSONAS.get(pid,{}); sc2 = entry.get("score"); col = entry.get("color","#888"); em = entry.get("emoji","⚪")
        rk = "rank-1" if i==0 else "rank-2" if i==1 else "rank-3" if i==2 else ""
        if entry.get("has_data") and sc2 is not None:
            rsn = " / ".join(entry.get("reasons",[])[:3])
            p_cards.append(f'<div style="padding:14px;border-radius:12px;border:1px solid {col}40;background:{col}12;margin-bottom:8px" id="persona-{pid}"><div style="display:flex;justify-content:space-between;align-items:start;margin-bottom:6px"><div style="display:flex;align-items:center;gap:8px"><span style="font-size:22px">{em}</span><div><div style="font-weight:700;color:{col}">{pid}</div><div style="font-size:11px;color:#666">{pdef.get("desc","")}</div></div></div><div style="font-size:22px;font-weight:900;color:{_c(sc2)}" id="pscore-{pid}">{sc2}<span style="font-size:13px">分</span></div></div><div style="font-size:11px;color:#555;margin-top:-4px;margin-bottom:6px">{rsn}</div>')
        else:
            p_cards.append(f'<div style="padding:14px;border-radius:12px;border:1px solid #222;background:#0f0f1a;margin-bottom:8px"><div style="display:flex;align-items:center;gap:8px"><span style="font-size:22px">{em}</span><div style="font-weight:700;color:#555">{pid}</div></div><div style="font-size:11px;color:#444;margin-top:4px">数据不足</div></div>')
    persona_html = "".join(p_cards) if p_cards else '<div style="text-align:center;color:#555;padding:20px;font-size:13px">数据不足，无法评测</div>'

    # radar data
    rl = ["感知","认知","大脑","记忆","工具","主动","输出","平台"]
    rk2 = ["perception","cognition","brain","memory","tools","proactive","output","platform"]
    rd = [str(round(radar.get(k,0) or 0,1)) for k in rk2]
    bv_d = str(brain)+"%" if brain is not None else "—"
    mv_d = str(mem_hit)+"%" if mem_hit is not None else "—"

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🦞 小龙虾能力仪表盘 v3</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
:root{{--bg:#080810;--c:#0f0f1a;--b:#1e1e2e}}
*{{font-family:system-ui,-apple-system,sans-serif;box-sizing:border-box}}
body{{background:var(--bg);color:#e0e0ee;margin:0;min-height:100vh}}
.card{{background:var(--c);border:1px solid var(--b);border-radius:16px;padding:20px}}
.st{{font-size:11px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:#555;margin-bottom:12px}}
.oc{{background:var(--c);border:1px solid var(--b);border-radius:12px;padding:14px 8px;text-align:center;transition:all .3s;cursor:default}}
.oc:hover{{border-color:#00d4ff;transform:translateY(-2px);box-shadow:0 6px 20px rgba(0,212,255,.1)}}
.mc{{background:var(--c);border:1px solid var(--b);border-radius:12px;padding:16px;text-align:center;transition:all .3s}}
.pulse{{animation:pulse 2s ease-in-out infinite}}
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.3}}}}
.flash{{animation:flash .5s ease}}
@keyframes flash{{0%{{background:rgba(0,212,255,.2)}}100%{{background:transparent}}}}
.rank-1{{border-color:rgba(255,215,0,.4)!important}}
.rank-2{{border-color:rgba(192,192,192,.4)!important}}
.rank-3{{border-color:rgba(205,127,50,.4)!important}}
</style>
</head>
<body>
<div class="max-w-7xl mx-auto p-5">

<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px">
 <div>
  <h1 style="font-size:20px;font-weight:700">🦞 小龙虾能力仪表盘 <span style="font-size:12px;color:#00d4ff;font-weight:400">v3.0</span></h1>
  <p style="font-size:12px;color:#555;margin-top:4px">真实数据 · 无预设值 · 动态更新</p>
 </div>
 <div style="display:flex;align-items:center;gap:12px">
  <div style="display:inline-flex;align-items:center;gap:6px;background:rgba(0,255,136,.08);border:1px solid rgba(0,255,136,.25);color:#00ff88;padding:4px 12px;border-radius:20px;font-size:11px;font-weight:600">
   <span class="pulse" style="width:7px;height:7px;background:#00ff88;border-radius:50%;display:inline-block"></span>LIVE · 5s
  </div>
  <button onclick="fetchData()" style="background:rgba(0,212,255,.1);border:1px solid rgba(0,212,255,.3);color:#00d4ff;padding:5px 12px;border-radius:8px;cursor:pointer;font-size:12px">🔄 刷新</button>
  <div id="ts" style="font-size:11px;color:#555">{ts}</div>
 </div>
</div>

<!-- 4个核心指标 -->
<div style="display:grid;grid-template-columns:2fr 1fr 1fr 1fr;gap:12px;margin-bottom:14px">
 <div class="card" style="text-align:center" id="oc">
  <div style="font-size:52px;font-weight:900;color:{ov_c};text-shadow:0 0 30px {ov_c}" id="ov">{ov_d}</div>
  <div style="font-size:12px;color:#555;margin-top:4px">综合评分</div>
 </div>
 <div class="mc">
  <div style="font-size:32px;font-weight:900;color:{sm_c}" id="sv">{sm_d}</div>
  <div style="font-size:12px;color:#555;margin-top:4px">丝滑等级</div>
  <div style="font-size:11px;color:#444;margin-top:2px">不打断用户</div>
 </div>
 <div class="mc">
  <div style="font-size:32px;font-weight:900;color:{ss_c}" id="ssv">{ss_d}</div>
  <div style="font-size:12px;color:#555;margin-top:4px">无缝衔接</div>
  <div style="font-size:11px;color:#444;margin-top:2px">器官协作成功率</div>
 </div>
 <div class="mc">
  <div style="font-size:32px;font-weight:900;color:{st_c}" id="stv">{st_d}</div>
  <div style="font-size:12px;color:#555;margin-top:4px">稳定丝滑</div>
  <div style="font-size:11px;color:#444;margin-top:2px">连续执行能力</div>
 </div>
</div>

<!-- 无缝衔接详情 & 雷达 -->
<div style="display:grid;grid-template-columns:1fr 220px;gap:14px;margin-bottom:14px">
 <div class="card">
  <div class="st">🔗 无缝衔接详情</div>
  <div id="seamlessDetail">{seam_detail_html}</div>
 </div>
 <div class="card" style="display:flex;align-items:center;justify-content:center">
  <canvas id="rc" width="200" height="200"></canvas>
 </div>
</div>

<!-- 器官 -->
<div class="card" style="margin-bottom:14px">
 <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
  <div class="st" style="margin:0">🔬 器官真实数据</div>
  <div style="font-size:11px;color:#555">累计≥5次出分数</div>
 </div>
 <div style="display:grid;grid-template-columns:repeat(7,1fr);gap:10px">{org_html}</div>
 <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:14px;padding-top:14px;border-top:1px solid #1e1e2e">
  <div style="text-align:center">
   <div style="font-size:18px;font-weight:700;color:{bv_c}" id="bv">{bv_d}</div>
   <div style="font-size:12px;color:#555">大脑采纳率</div>
  </div>
  <div style="text-align:center">
   <div style="font-size:18px;font-weight:700;color:{mv_c}" id="mv">{mv_d}</div>
   <div style="font-size:12px;color:#555">记忆命中率</div>
  </div>
  <div style="text-align:center">
   <div style="font-size:18px;font-weight:700;color:#555" id="dp">{d.get("data_points",0)}</div>
   <div style="font-size:12px;color:#555">有效数据指标</div>
  </div>
 </div>
</div>

<!-- 缺口 & 人格 -->
<div style="display:grid;grid-template-columns:1fr 1.2fr;gap:14px">
 <div class="card">
  <div class="st" style="margin-bottom:8px">⚠️ 待升级能力缺口</div>
  <div style="font-size:11px;color:#555;margin-bottom:10px">真实遇到的问题自动记录</div>
  <div id="gapsContainer">{gaps_html}</div>
 </div>
 <div class="card">
  <div class="st" style="margin-bottom:8px">🎭 职业人格测评</div>
  <div style="font-size:11px;color:#555;margin-bottom:10px">基于真实能力数据 · 匹配度评分</div>
  <div id="personasContainer">{persona_html}</div>
 </div>
</div>

<div style="text-align:center;color:#444;font-size:11px;margin-top:24px">
 每5秒刷新 · 数据来自 task_recorder / memory_probe / reasoning_probe / gap_recorder
</div>
</div>

<script>
var rc=null,lastTs="";
async function fetchData(){{
 try{{
  var r=await fetch("/api/dashboard?t="+Date.now());
  if(!r.ok)return;
  var d=await r.json();
  if(d.generated_at===lastTs)return;
  lastTs=d.generated_at;
  updateUI(d);
 }}catch(e){{document.getElementById("ts").textContent="等待数据...";}}
}}
function gc(v){{
 if(v===null||v===undefined)return"#555";
 if(v>=80)return"#00ff88";
 if(v>=60)return"#00d4ff";
 if(v>=40)return"#ffd700";return"#ff4466";
}}
function updateUI(d){{
 document.getElementById("ts").textContent=d.generated_at.slice(0,19);
 var ov=d.overall_score;
 if(ov!==null){{
  var oc=gc(ov);
  var oel=document.getElementById("ov");
  oel.textContent=ov;oel.style.color=oc;oel.style.textShadow="0 0 30px "+oc;
  var card=document.getElementById("oc");card.classList.remove("flash");void card.offsetWidth;card.classList.add("flash");
 }}
 var sv=d.smooth_score;
 var sel=document.getElementById("sv");
 if(sel){{sel.textContent=(sv!==null?sv+"%":"—");sel.style.color=gc(sv);}}
 var ss=d.seamless_score;
 var ssv=document.getElementById("ssv");
 if(ssv){{ssv.textContent=(ss!==null?ss+"%":"未检测");ssv.style.color=gc(ss);}}
 var st=d.stability_score;
 var stv=document.getElementById("stv");
 if(stv){{stv.textContent=(st!==null?st+"%":"未检测");stv.style.color=gc(st);}}
 var bv=d.brain_score;
 var bvel=document.getElementById("bv");
 if(bvel){{bvel.textContent=(bv!==null?bv+"%":"—");bvel.style.color=gc(bv);}}
 var mv=d.memory_hit_rate;
 var mvel=document.getElementById("mv");
 if(mvel){{mvel.textContent=(mv!==null?mv+"%":"—");mvel.style.color=gc(mv);}}
 var dp=document.getElementById("dp");
 if(dp)dp.textContent=d.data_points||0;
 var orgs=d.organs||{{}};
 ["眼睛","耳朵","大脑","记忆","嘴巴","工具","手脚"].forEach(function(n){{
  var info=orgs[n]||{{}};
  var sc=info.score;var has=info.has_data;
  var sel=document.getElementById("score-"+n);
  if(has&&sc!==null&&sel){{sel.textContent=sc;sel.style.color=gc(sc);}}
 }});
 updateRadar(d.radar||{{}});
}}
function updateRadar(r){{
 var labels=["感知","认知","大脑","记忆","工具","主动","输出","平台"];
 var keys=["perception","cognition","brain","memory","tools","proactive","output","platform"];
 var vals=keys.map(function(k){{return r[k]||0;}});
 var ctx=document.getElementById("rc");
 if(!ctx)return;
 if(!rc){{
  rc=new Chart(ctx,{{
   type:"radar",
   data:{{labels:labels,datasets:[{{data:vals,backgroundColor:"rgba(0,212,255,0.12)",borderColor:"#00d4ff",borderWidth:2,pointBackgroundColor:"#00d4ff",pointRadius:4}}]}},
   options:{{responsive:true,scales:{{r:{{beginAtZero:true,max:10,stepSize:2,ticks:{{color:"#444",backdropColor:"transparent",font:{{size:9}}}},grid:{{color:"rgba(255,255,255,0.07)"}},angleLines:{{color:"rgba(255,255,255,0.07)"}},pointLabels:{{color:"#666",font:{{size:10}}}}}},plugins:{{legend:{{display:false}}}}}}
  }});
 }}else{{rc.data.datasets[0].data=vals;rc.update("none");}}
}}
fetchData();
setInterval(fetchData,5000);
</script>
</body>
</html>'''
    return html

if __name__=="__main__":
    import socket
    s=socket.socket();r=s.connect_ex(("0.0.0.0",PORT));s.close()
    if r==0:
        print(f"端口{PORT}已被占用，仪表盘已在运行: http://localhost:{PORT}")
        sys.exit(1)
    print(f"╔═══════════════════════════╗\n║  🦞 http://localhost:{PORT}   ║\n╚═══════════════════════════╝")
    with socketserver.TCPServer(("0.0.0.0",PORT),Handler) as httpd:
        httpd.serve_forever()
