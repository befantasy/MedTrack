# -*- coding: utf-8 -*-
import csv
from datetime import datetime, timedelta, timezone
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

from http.cookiejar import DefaultCookiePolicy
import pandas as pd
import plotly.express as px
import requests
from requests.adapters import HTTPAdapter
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="CF 缓存预热与长效监控看板", layout="wide")
st.title("Cloudflare HTML 缓存预热与长效监控看板")

# 定义北京时间 (UTC+8) 时区
BEIJING_TZ = timezone(timedelta(hours=8))

DATA_FILE = "cache_progress.csv"            # 页面明细记录文件 (带 Run_ID)
SUMMARY_FILE = "cache_runs_summary.csv"     # 轮次汇总统计历史文件
LOCK = threading.Lock()

# 统一状态配色映射表
STATUS_COLOR_MAP = {
    "HIT": "#10B981",          # 绿色 (完全命中)
    "UPDATING": "#06B6D4",     # 青色 (过时内容秒开，后台静默异步刷新)
    "STALE": "#F97316",        # 橙色 (源站异常或重验超时兜底交付)
    "MISS": "#EF4444",         # 红色 (穿透回源)
    "REVALIDATED": "#3B82F6",  # 蓝色 (同步协商 304)
    "EXPIRED": "#F59E0B",      # 黄色
    "DYNAMIC": "#6366F1",      # 靛青
    "BYPASS": "#8B5CF6",       # 紫色
    "ERROR": "#991B1B",        # 深红
    "UNKNOWN": "#9CA3AF"       # 灰色
}

# 状态中文释义映射表（用于悬停浮动提示）
STATUS_DESC_MAP = {
    "HIT": "完全命中",
    "UPDATING": "过时秒开/异步刷新",
    "STALE": "源站异常兜底交付",
    "MISS": "穿透回源",
    "REVALIDATED": "同步协商 304",
    "EXPIRED": "缓存过期",
    "DYNAMIC": "动态内容",
    "BYPASS": "绕过缓存",
    "ERROR": "请求异常",
    "UNKNOWN": "未知状态"
}

NON_HTML_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".webp", ".avif", ".gif", ".ico", ".svg",
    ".css", ".js", ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".xml", ".xsl", ".json", ".pdf", ".zip", ".tar", ".gz",
    ".mp3", ".mp4", ".wav", ".webm", ".txt", ".csv"
)

# 页面明细表字段 (增加 Run_ID 标识轮次)
CSV_COLUMNS = ["Run_ID", "URL", "CF-Status", "CF-Node", "Code", "Latency(ms)", "Cache-Control", "Age", "Checked_At"]

# 轮次汇总统计表字段
SUMMARY_COLUMNS = [
    "Run_ID", "Started_At", "Finished_At", "Total_Pages", "Hit_Rate(%)",
    "HIT", "UPDATING", "STALE", "REVALIDATED", "EXPIRED", "MISS", "ERROR",
    "Avg_TTFB(ms)", "Top_Node"
]

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Referer": "https://medfind.link/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

def safe_read_csv(filepath, default_columns):
    """
    通用高容错 CSV 读取函数：
    依次尝试 utf-8-sig, utf-8, gbk, gb18030 兼容 Windows/Excel 多编码环境，
    最后使用 encoding_errors='replace' 兜底，彻底杜绝 UnicodeDecodeError
    """
    if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
        return pd.DataFrame(columns=default_columns)
    
    encodings_to_try = ["utf-8-sig", "utf-8", "gbk", "gb18030"]
    for enc in encodings_to_try:
        try:
            with LOCK:
                df = pd.read_csv(filepath, encoding=enc, on_bad_lines="skip")
            for col in default_columns:
                if col not in df.columns:
                    df[col] = "-"
            return df
        except UnicodeDecodeError:
            continue
        except Exception:
            break
            
    # 极端异常字节兜底策略：替换乱码字符，确保系统绝对不崩溃
    try:
        with LOCK:
            df = pd.read_csv(filepath, encoding="utf-8", encoding_errors="replace", on_bad_lines="skip")
        for col in default_columns:
            if col not in df.columns:
                df[col] = "-"
        return df
    except Exception:
        return pd.DataFrame(columns=default_columns)

@st.cache_resource
def get_http_session():
    session = requests.Session()
    # 连接池大小设为 20，底层不自动叠加重试，改由应用层精准独立计时
    adapter = HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=0)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.cookies.set_policy(DefaultCookiePolicy(allowed_domains=[]))
    return session

session = get_http_session()

@st.cache_resource
def get_task_state():
    return {
        "running": False,
        "stop_signal": False,
        "total": 0,
        "current": 0,
        "current_run_id": "",
        "msg": "",
        "need_final_rerun": False
    }

state = get_task_state()

@st.cache_resource
def get_scheduler_state():
    return {
        "enabled": False,
        "interval_hours": 1.0,
        "next_run_time": None,
        "last_run_time": None,
        "sitemap_url": "https://medfind.link/sitemap_index.xml",
        "workers": 5,
        "daemon_started": False
    }

scheduler = get_scheduler_state()

def is_html_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    if not path or path.endswith("/") or path.endswith((".html", ".htm")):
        return True
    return not any(path.endswith(ext) for ext in NON_HTML_EXTENSIONS)

def parse_sitemap(url, headers):
    urls = []
    try:
        r = session.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            return []
        root = ET.fromstring(r.content)
        if root.tag.endswith("sitemapindex"):
            for elem in root.iter():
                tag = elem.tag.lower()
                if tag.endswith("loc") and "image" not in tag and "video" not in tag and elem.text:
                    urls.extend(parse_sitemap(elem.text.strip(), headers))
        elif root.tag.endswith("urlset"):
            for elem in root.iter():
                tag = elem.tag.lower()
                if tag.endswith("loc") and "image" not in tag and "video" not in tag and elem.text:
                    link = elem.text.strip()
                    if is_html_url(link):
                        urls.append(link)
    except Exception:
        pass
    return list(set(urls))

def check_and_save(run_id, url, headers, max_retries=1):
    dur, cf, cf_node, cache_control, age, code = 0, "ERROR", "UNKNOWN", "-", "-", 0
    # 显式重试循环：若第 1 次超时/断连，第 2 次重试会重新独立计算时间，不再叠加耗时
    for attempt in range(max_retries + 1):
        try:
            r = session.get(url, headers=headers, timeout=8)
            # 使用 requests 原生 r.elapsed 计算精确的首包时间 (TTFB)，完全排除网页体积与网络下载耗时干扰
            dur = round(r.elapsed.total_seconds() * 1000, 1)
            cf = r.headers.get("cf-cache-status", "UNKNOWN").upper()
            
            # 提取边缘节点 IATA 机场代码
            cf_ray = r.headers.get("cf-ray", "")
            cf_node = cf_ray.split("-")[-1].strip().upper() if "-" in cf_ray else "UNKNOWN"
            
            cache_control = r.headers.get("cache-control", "-")
            age = r.headers.get("age", "-")
            code = r.status_code
            break  # 本次成功，跳出重试循环，dur 即为本次请求的精确 TTFB
        except Exception:
            dur = 0
            if attempt == max_retries:
                cf, cf_node, cache_control, age, code = "ERROR", "UNKNOWN", "-", "-", 0
    
    current_time_beijing = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")
    with LOCK:
        with open(DATA_FILE, mode="a", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow([run_id, url, cf, cf_node, code, dur, cache_control, age, current_time_beijing])
    return True

def cleanup_7days_data():
    """自动滚动淘汰超过 7 天的历史数据 (明细表与轮次汇总表)"""
    cutoff = datetime.now(BEIJING_TZ) - timedelta(days=7)
    cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")
    with LOCK:
        # 清理轮次汇总表
        if os.path.exists(SUMMARY_FILE):
            try:
                df_s = safe_read_csv(SUMMARY_FILE, SUMMARY_COLUMNS)
                if "Started_At" in df_s.columns and not df_s.empty:
                    df_s = df_s[df_s["Started_At"] >= cutoff_str]
                    df_s.to_csv(SUMMARY_FILE, index=False, encoding="utf-8-sig")
            except Exception:
                pass
        # 清理页面明细表
        if os.path.exists(DATA_FILE):
            try:
                df_p = safe_read_csv(DATA_FILE, CSV_COLUMNS)
                if "Checked_At" in df_p.columns and not df_p.empty:
                    df_p = df_p[df_p["Checked_At"] >= cutoff_str]
                    df_p.to_csv(DATA_FILE, index=False, encoding="utf-8-sig")
            except Exception:
                pass

def record_run_summary(run_id, started_at_str):
    """当一轮测试执行完毕后，自动汇总该轮次统计指标并落盘到汇总表"""
    finished_at_str = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")
    try:
        df_all = safe_read_csv(DATA_FILE, CSV_COLUMNS)
        df_run = df_all[df_all["Run_ID"] == run_id] if "Run_ID" in df_all.columns else df_all
        if df_run.empty:
            return
        
        total_pages = len(df_run)
        counts = df_run["CF-Status"].value_counts()
        hit = int(counts.get("HIT", 0))
        updating = int(counts.get("UPDATING", 0))
        stale = int(counts.get("STALE", 0))
        revalidated = int(counts.get("REVALIDATED", 0))
        expired = int(counts.get("EXPIRED", 0))
        miss = int(counts.get("MISS", 0))
        error = int(counts.get("ERROR", 0))
        
        effective_hits = hit + updating + stale
        hit_rate = round((effective_hits / total_pages) * 100, 1) if total_pages > 0 else 0.0
        
        # 计算有效首包平均延迟 (TTFB)
        valid_latencies = pd.to_numeric(df_run["Latency(ms)"], errors="coerce").dropna()
        valid_latencies = valid_latencies[valid_latencies > 0]
        avg_ttfb = round(valid_latencies.mean(), 1) if not valid_latencies.empty else 0.0
        
        # 统计最主要的边缘节点
        valid_nodes = df_run[~df_run["CF-Node"].isin(["-", "UNKNOWN", ""])]["CF-Node"]
        top_node = valid_nodes.mode()[0] if not valid_nodes.empty else "无"
        
        row_summary = [
            run_id, started_at_str, finished_at_str, total_pages, hit_rate,
            hit, updating, stale, revalidated, expired, miss, error,
            avg_ttfb, top_node
        ]
        
        with LOCK:
            file_exists = os.path.exists(SUMMARY_FILE) and os.path.getsize(SUMMARY_FILE) > 0
            with open(SUMMARY_FILE, mode="a", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(SUMMARY_COLUMNS)
                writer.writerow(row_summary)
        
        # 自动触发一次 7 天超期数据滚动清理
        cleanup_7days_data()
    except Exception as e:
        print(f"写入轮次汇总异常: {e}")

def background_worker(run_id, urls, headers, workers, started_at_str):
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for _ in executor.map(lambda u: check_and_save(run_id, u, headers) if not state["stop_signal"] else False, urls):
            if state["stop_signal"]:
                break
            state["current"] += 1
    state["running"] = False
    state["stop_signal"] = False
    state["need_final_rerun"] = True  # 后台完全结束，点亮收尾标记
    
    # 汇总并保存本轮次的统计数据
    record_run_summary(run_id, started_at_str)

def start_new_test_run(sitemap_url, workers):
    """启动一轮全新的全站测速与预热"""
    if state["running"]:
        return False
    started_at = datetime.now(BEIJING_TZ)
    started_at_str = started_at.strftime("%Y-%m-%d %H:%M:%S")
    run_id = started_at.strftime("%Y-%m-%d %H:%M:%S")
    
    all_urls = parse_sitemap(sitemap_url, DEFAULT_HEADERS)
    if not all_urls:
        return False
    
    state["running"] = True
    state["stop_signal"] = False
    state["need_final_rerun"] = False
    state["current_run_id"] = run_id
    state["total"] = len(all_urls)
    state["current"] = 0
    
    threading.Thread(
        target=background_worker,
        args=(run_id, all_urls, DEFAULT_HEADERS, workers, started_at_str),
        daemon=True
    ).start()
    return True

def scheduler_daemon_loop():
    """后台常驻守护线程：按设定间隔自动发起全站测试"""
    while True:
        time.sleep(10)
        try:
            if scheduler["enabled"] and scheduler["next_run_time"]:
                now = datetime.now(BEIJING_TZ)
                if now >= scheduler["next_run_time"]:
                    if not state["running"]:
                        success = start_new_test_run(scheduler["sitemap_url"], scheduler["workers"])
                        if success:
                            scheduler["last_run_time"] = now
                            scheduler["next_run_time"] = now + timedelta(hours=scheduler["interval_hours"])
        except Exception:
            pass

# 确保后台调度守护线程只启动一次
if not scheduler.get("daemon_started", False):
    scheduler["daemon_started"] = True
    threading.Thread(target=scheduler_daemon_loop, daemon=True).start()

def init_storage_files():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, mode="w", newline="", encoding="utf-8-sig") as f:
            csv.writer(f).writerow(CSV_COLUMNS)
    if not os.path.exists(SUMMARY_FILE):
        with open(SUMMARY_FILE, mode="w", newline="", encoding="utf-8-sig") as f:
            csv.writer(f).writerow(SUMMARY_COLUMNS)

init_storage_files()

# 安全高容错读取数据
df_done = safe_read_csv(DATA_FILE, CSV_COLUMNS)
if "Run_ID" not in df_done.columns:
    df_done["Run_ID"] = "历史批次"

df_summary = safe_read_csv(SUMMARY_FILE, SUMMARY_COLUMNS)

# 确保数值字段转换正常
df_done["Latency(ms)"] = pd.to_numeric(df_done["Latency(ms)"], errors="coerce").fillna(0.0)

# ==============================================================================
# 区域 1：配置与控制面板（定时任务、手动控制、并发度与链接设置）
# ==============================================================================
with st.expander("任务设置与定时巡检配置 (支持自动按固定时间循环测试并滚动保留 7 天)", expanded=True):
    ctl_c1, ctl_c2, ctl_c3 = st.columns([1.2, 1.2, 1.6])
    
    with ctl_c1:
        sitemap_input = st.text_input("Sitemap 地址", value=scheduler.get("sitemap_url", "https://medfind.link/sitemap_index.xml"))
        scheduler["sitemap_url"] = sitemap_input
        workers = st.slider("并发线程数", min_value=1, max_value=10, value=scheduler.get("workers", 5))
        scheduler["workers"] = workers

    with ctl_c2:
        # 定时测试开关
        sched_enabled = st.toggle("开启定时自动测试", value=scheduler["enabled"])
        if sched_enabled != scheduler["enabled"]:
            scheduler["enabled"] = sched_enabled
            if sched_enabled:
                now = datetime.now(BEIJING_TZ)
                # 开启时计算下次触发时间：若有历史执行时间则智能顺延，否则从当前时间起算
                if scheduler.get("last_run_time"):
                    candidate = scheduler["last_run_time"] + timedelta(hours=scheduler["interval_hours"])
                    scheduler["next_run_time"] = candidate if candidate > now else now
                else:
                    scheduler["next_run_time"] = now + timedelta(hours=scheduler["interval_hours"])
            else:
                scheduler["next_run_time"] = None
            st.rerun()

        interval_options = [0.5, 1.0, 2.0, 4.0, 6.0, 8.0, 12.0, 24.0]
        curr_interval = scheduler.get("interval_hours", 1.0)
        curr_idx = interval_options.index(curr_interval) if curr_interval in interval_options else 1
        selected_interval = st.selectbox(
            "自动测试间隔时间",
            options=interval_options,
            index=curr_idx,
            format_func=lambda h: f"{int(h*60)} 分钟" if h < 1 else f"{int(h)} 小时"
        )
        # 随时调整间隔即时生效：无论是开启前还是运行中修改，都立即重新计算下次测试时间
        if selected_interval != scheduler["interval_hours"]:
            scheduler["interval_hours"] = selected_interval
            if scheduler["enabled"]:
                now = datetime.now(BEIJING_TZ)
                if scheduler.get("last_run_time"):
                    candidate = scheduler["last_run_time"] + timedelta(hours=selected_interval)
                    scheduler["next_run_time"] = candidate if candidate > now else now
                else:
                    scheduler["next_run_time"] = now + timedelta(hours=selected_interval)
            st.rerun()

    with ctl_c3:
        st.markdown("**调度与控制状态**")
        if scheduler["enabled"] and scheduler["next_run_time"]:
            remain_seconds = max(0, int((scheduler["next_run_time"] - datetime.now(BEIJING_TZ)).total_seconds()))
            m, s = divmod(remain_seconds, 60)
            h, m = divmod(m, 60)
            time_str = f"{h:02d}小时 {m:02d}分 {s:02d}秒" if h > 0 else f"{m:02d}分 {s:02d}秒"
            st.success(f"[运行中] 下次测试于: {scheduler['next_run_time'].strftime('%H:%M:%S')} (倒计时: {time_str})")
        else:
            st.info("[已停用] 定时任务未开启（可开启左侧开关启用自动巡检）")

        btn_c1, btn_c2, btn_c3 = st.columns(3)
        if not state["running"]:
            if btn_c1.button("[>] 立即测一轮", use_container_width=True):
                with st.spinner("正在解析 Sitemap 并启动测试..."):
                    ok = start_new_test_run(sitemap_input, workers)
                    if ok:
                        if scheduler["enabled"]:
                            now = datetime.now(BEIJING_TZ)
                            scheduler["last_run_time"] = now
                            scheduler["next_run_time"] = now + timedelta(hours=scheduler["interval_hours"])
                        st.rerun()
                    else:
                        st.error("未能从给定的 Sitemap 获取到有效页面。")
            if btn_c2.button("[X] 清空历史", use_container_width=True, help="清空 7 天明细与轮次汇总数据"):
                with LOCK:
                    with open(DATA_FILE, mode="w", newline="", encoding="utf-8-sig") as f:
                        csv.writer(f).writerow(CSV_COLUMNS)
                    with open(SUMMARY_FILE, mode="w", newline="", encoding="utf-8-sig") as f:
                        csv.writer(f).writerow(SUMMARY_COLUMNS)
                st.success("已重置所有历史记录！")
                st.rerun()
        else:
            if btn_c1.button("[!] 停止测试", use_container_width=True):
                state["stop_signal"] = True
                st.warning("正在停止测试任务...")

        with btn_c3:
            st.download_button(
                label="[导出] 明细CSV",
                data=df_done.to_csv(index=False).encode("utf-8-sig"),
                file_name="cache_details_7days.csv",
                mime="text/csv",
                use_container_width=True
            )

# 实时进度条
if state["running"]:
    st.info(f"[执行中] 正在执行测试轮次【{state['current_run_id']}】...")
    if state["total"] > 0:
        pct = min(1.0, state["current"] / state["total"])
        st.progress(pct)
        st.caption(f"当前进度：{state['current']} / {state['total']} ({round(pct * 100, 1)}%)")

# ==============================================================================
# 区域 2：历史测试轮次列表（每行代表一次测试，列展示该次的统计数据，点击行即可回溯）
# ==============================================================================
st.subheader("历史测试轮次列表 (点击行即可回溯查看该次测试的完整现场，滚动保留最近7天)")

selected_run_id = None

if not df_summary.empty:
    # 确保排序：最新测试轮次在最上方
    df_summary_display = df_summary.copy()
    if "Started_At" in df_summary_display.columns:
        df_summary_display = df_summary_display.sort_values(by="Started_At", ascending=False).reset_index(drop=True)
    
    # 构造友好的展示列名
    rename_dict = {
        "Run_ID": "轮次批次",
        "Started_At": "开始时间",
        "Finished_At": "完成时间",
        "Total_Pages": "页面数",
        "Hit_Rate(%)": "有效命中率(%)",
        "HIT": "HIT",
        "UPDATING": "UPDATING",
        "STALE": "STALE",
        "REVALIDATED": "REVALIDATED",
        "EXPIRED": "EXPIRED",
        "MISS": "MISS",
        "ERROR": "ERROR",
        "Avg_TTFB(ms)": "平均TTFB(ms)",
        "Top_Node": "主要节点"
    }
    cols_to_show = [col for col in rename_dict.keys() if col in df_summary_display.columns]
    table_df = df_summary_display[cols_to_show].rename(columns=rename_dict)

    # 交互式数据表格：支持直接点击单行选中轮次
    try:
        selection = st.dataframe(
            table_df,
            use_container_width=True,
            selection_mode="single-row",
            on_select="rerun",
            hide_index=True
        )
        if selection and hasattr(selection, "selection") and selection.selection.rows:
            selected_idx = selection.selection.rows[0]
            selected_run_id = str(df_summary_display.iloc[selected_idx]["Run_ID"])
    except Exception:
        st.dataframe(table_df, use_container_width=True, hide_index=True)

    # 如果未手动点击表格某一行，默认选择最新的一轮测试
    if not selected_run_id and not df_summary_display.empty:
        selected_run_id = str(df_summary_display.iloc[0]["Run_ID"])

    # 同时提供快捷单选行辅助切换
    run_list = df_summary_display["Run_ID"].tolist()
    if len(run_list) > 1:
        default_index = run_list.index(selected_run_id) if selected_run_id in run_list else 0
        pick_run = st.radio(
            "快捷切换查看轮次：",
            options=run_list,
            index=default_index,
            format_func=lambda r: f"批次: {r} (命中率: {df_summary_display[df_summary_display['Run_ID']==r]['Hit_Rate(%)'].values[0]}% | {df_summary_display[df_summary_display['Run_ID']==r]['Total_Pages'].values[0]} 页)",
            horizontal=True
        )
        selected_run_id = pick_run
else:
    # 如果还没有汇总历史（比如刚跑过一次旧版明细），则从明细表中提取 Run_ID
    if "Run_ID" in df_done.columns and not df_done.empty:
        available_runs = df_done["Run_ID"].unique().tolist()
        if available_runs:
            selected_run_id = available_runs[-1]
    st.info("暂无完成的轮次历史汇总，点击上方「[>] 立即测一轮」或开启定时测试后将自动记录每轮快照。")

# ==============================================================================
# 区域 3：7 天历史走势折线图 (命中率 & 平均首包 TTFB 趋势)
# ==============================================================================
if not df_summary.empty and len(df_summary) >= 2:
    with st.expander("近 7 天全站缓存命中率与平均 TTFB 延迟走势", expanded=False):
        df_trend = df_summary.copy()
        if "Started_At" in df_trend.columns:
            df_trend = df_trend.sort_values(by="Started_At", ascending=True)
            df_trend["Hit_Rate(%)"] = pd.to_numeric(df_trend["Hit_Rate(%)"], errors="coerce")
            df_trend["Avg_TTFB(ms)"] = pd.to_numeric(df_trend["Avg_TTFB(ms)"], errors="coerce")
            
            trend_c1, trend_c2 = st.columns(2)
            fig_trend_hit = px.line(
                df_trend, x="Started_At", y="Hit_Rate(%)",
                markers=True, title="7天全站有效缓存命中率变化趋势 (%)",
                color_discrete_sequence=["#10B981"]
            )
            trend_c1.plotly_chart(fig_trend_hit, use_container_width=True)

            fig_trend_ttfb = px.line(
                df_trend, x="Started_At", y="Avg_TTFB(ms)",
                markers=True, title="7天平均首包延迟 (TTFB) 变化走势 (ms)",
                color_discrete_sequence=["#3B82F6"]
            )
            trend_c2.plotly_chart(fig_trend_ttfb, use_container_width=True)

# ==============================================================================
# 区域 4：所选测试轮次的完整快照看板 (现场回溯)
# ==============================================================================
st.markdown("---")

# 筛选所选轮次的明细数据
if selected_run_id and "Run_ID" in df_done.columns:
    df_current_run = df_done[df_done["Run_ID"] == selected_run_id]
else:
    df_current_run = df_done

if not df_current_run.empty:
    st.markdown(f"### [现场快照] 当前展示测试轮次：`{selected_run_id if selected_run_id else '当前记录'}`")
    
    counts = df_current_run["CF-Status"].value_counts()
    hit_num = counts.get("HIT", 0)
    updating_num = counts.get("UPDATING", 0)
    stale_num = counts.get("STALE", 0)
    reval_num = counts.get("REVALIDATED", 0)
    expired_num = counts.get("EXPIRED", 0)
    miss_num = counts.get("MISS", 0)
    total_tested = len(df_current_run)
    
    # 真实边缘交付命中率：HIT、UPDATING、STALE 均属于秒级直接交付
    effective_hits = hit_num + updating_num + stale_num
    hit_rate = round((effective_hits / total_tested) * 100, 1) if total_tested > 0 else 0.0

    # 统计节点信息
    valid_nodes = df_current_run[~df_current_run["CF-Node"].isin(["-", "UNKNOWN", ""])]["CF-Node"]
    unique_nodes_count = valid_nodes.nunique()
    top_node = valid_nodes.mode()[0] if not valid_nodes.empty else "无"

    # 第一行指标卡（7 列）
    m1, m2, m3, m4, m5, m6, m7 = st.columns(7)
    m1.metric("已落盘页面数", f"{total_tested}")
    m2.metric("有效缓存命中率", f"{hit_rate}%", help="包含 HIT、UPDATING 与 STALE（均为边缘零延迟直接交付）")
    m3.metric("HIT / UPDATING", f"{hit_num} / {updating_num}")
    m4.metric("REVALIDATED", f"{reval_num}")
    m5.metric("EXPIRED", f"{expired_num}")
    m6.metric("MISS", f"{miss_num}")
    m7.metric("命中节点数 (主要节点)", f"{unique_nodes_count} ({top_node})")

    # 第一行图表：缓存状态与 TTFB 延迟
    chart_c1, chart_c2 = st.columns(2)
    
    # 汇总各状态页面计数、全站占比与中文描述（供饼图及右侧图例悬停展示）
    df_status = df_current_run["CF-Status"].value_counts().reset_index()
    df_status.columns = ["CF-Status", "Count"]
    total_status_count = df_status["Count"].sum()
    df_status["Percent"] = df_status["Count"].apply(
        lambda c: round((c / total_status_count) * 100, 1) if total_status_count > 0 else 0.0
    )
    df_status["Status_Label"] = df_status["CF-Status"].map(
        lambda s: f"{s} ({STATUS_DESC_MAP.get(s, '')})" if s in STATUS_DESC_MAP else str(s)
    )

    # 保持原有纯净布局：names 依然为 CF-Status 原名，图例保持清爽
    fig_pie = px.pie(
        df_status,
        names="CF-Status",
        values="Count",
        title="缓存状态分布比例",
        hole=0.4,
        color="CF-Status",
        color_discrete_map=STATUS_COLOR_MAP,
        custom_data=["Status_Label"]
    )
    # 配置扇区悬停浮动计数卡
    fig_pie.update_traces(
        textposition="inside",
        textinfo="percent+label",
        hovertemplate="<b>缓存状态</b>: %{customdata[0]}<br><b>页面计数</b>: %{value:,} 条<br><b>占比</b>: %{percent}<extra></extra>"
    )
    fig_pie.update_layout(
        hoverlabel=dict(
            bgcolor="rgba(255, 255, 255, 0.95)",
            font_size=13,
            font_color="#1f2937"
        )
    )
    chart_c1.plotly_chart(fig_pie, use_container_width=True)

    fig_hist = px.histogram(
        df_current_run, x="Latency(ms)", color="CF-Status",
        title="首包响应延迟 (TTFB) 分布对比",
        color_discrete_map=STATUS_COLOR_MAP
    )
    fig_hist.update_traces(
        hovertemplate="<b>状态</b>: %{fullData.name}<br><b>TTFB 延迟</b>: %{x} ms<br><b>页面计数</b>: %{y:,} 条<extra></extra>"
    )
    fig_hist.update_layout(
        hoverlabel=dict(
            bgcolor="rgba(255, 255, 255, 0.95)",
            font_size=13,
            font_color="#1f2937"
        )
    )
    chart_c2.plotly_chart(fig_hist, use_container_width=True)

    # 第二行图表：节点请求占比与各节点状态分布透视
    node_c1, node_c2 = st.columns(2)
    fig_node_bar = px.histogram(
        df_current_run, x="CF-Node", title="各 Cloudflare 边缘节点请求量",
        color="CF-Node"
    )
    fig_node_bar.update_traces(
        hovertemplate="<b>边缘节点</b>: %{x}<br><b>请求总数</b>: %{y:,} 条<extra></extra>"
    )
    fig_node_bar.update_layout(
        hoverlabel=dict(
            bgcolor="rgba(255, 255, 255, 0.95)",
            font_size=13,
            font_color="#1f2937"
        )
    )
    node_c1.plotly_chart(fig_node_bar, use_container_width=True)

    fig_node_status = px.histogram(
        df_current_run, x="CF-Node", color="CF-Status", barmode="stack",
        title="各节点缓存状态穿透透视 (排查漂移与旧副本)",
        color_discrete_map=STATUS_COLOR_MAP
    )
    fig_node_status.update_traces(
        hovertemplate="<b>边缘节点</b>: %{x}<br><b>缓存状态</b>: %{fullData.name}<br><b>页面计数</b>: %{y:,} 条<extra></extra>"
    )
    fig_node_status.update_layout(
        hoverlabel=dict(
            bgcolor="rgba(255, 255, 255, 0.95)",
            font_size=13,
            font_color="#1f2937"
        )
    )
    node_c2.plotly_chart(fig_node_status, use_container_width=True)

    st.subheader(f"本轮已检测页面明细（共 {len(df_current_run)} 条记录）")
    st.dataframe(df_current_run.tail(100).iloc[::-1], use_container_width=True)

    # 为右侧图例增加原生悬停浮动计数提示 (使用 Array + String.fromCharCode 彻底杜绝换行失效)
    status_hover_dict = {
        str(row["CF-Status"]): [
            row["Status_Label"],
            f"页面计数: {row['Count']:,} 条",
            f"全站占比: {row['Percent']}%"
        ]
        for _, row in df_status.iterrows()
    }
    hover_json = json.dumps(status_hover_dict, ensure_ascii=False)
    components.html(
        f"""
        <script>
        (function() {{
            const statusMap = {hover_json};
            const newline = String.fromCharCode(13, 10);
            function updateLegendTooltips() {{
                try {{
                    const doc = window.parent.document;
                    const legendItems = doc.querySelectorAll('.legend .traces');
                    legendItems.forEach(item => {{
                        const textEl = item.querySelector('.legendtext');
                        if (textEl) {{
                            const key = textEl.textContent.trim();
                            if (statusMap[key]) {{
                                const lines = statusMap[key];
                                const formattedText = Array.isArray(lines) ? lines.join(newline) : String(lines);
                                let titleEl = item.querySelector('title');
                                if (!titleEl) {{
                                    titleEl = doc.createElementNS('http://www.w3.org/2000/svg', 'title');
                                    item.appendChild(titleEl);
                                }}
                                titleEl.textContent = formattedText;
                                item.setAttribute('title', formattedText);
                                textEl.setAttribute('title', formattedText);
                            }}
                        }}
                    }});
                }} catch (e) {{}}
            }}
            updateLegendTooltips();
            setInterval(updateLegendTooltips, 800);
        }})();
        </script>
        """,
        height=0,
        width=0
    )
else:
    st.info("当前尚未包含测试数据，请在上方点击「[>] 立即测一轮」或开启定时测试。")

# ==============================================================================
# 调度逻辑：测试运行中按 5 秒重绘；任务收尾时触发一次 100% 重绘；开启定时时按 10 秒刷新倒计时
# ==============================================================================
if state["running"]:
    time.sleep(5)
    st.rerun()
elif state.get("need_final_rerun", False):
    state["need_final_rerun"] = False
    st.rerun()
elif scheduler.get("enabled", False):
    time.sleep(10)
    st.rerun()

