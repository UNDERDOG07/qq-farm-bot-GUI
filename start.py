# start.py

from nicegui import ui
import subprocess
import threading
import os
import signal
import time
import re
import json
from pathlib import Path
from collections import defaultdict
import asyncio

# ====================== 全局 UI 组件（避免 NameError） ======================
status = None
user_info_label = None
gold_label = None
level_label = None
steal_label = None
harvest_label = None
exp_gain_label = None
analysis_table = None
log_container = None

# ====================== 配置 ======================
BOT_DIR = Path('.')  # start.py 放在 qq-farm-bot 根目录下
NODE_CMD = 'node'
MAIN_SCRIPT = 'client.js'
PID_FILE = BOT_DIR / 'bot.pid'
STATUS_FILE = BOT_DIR / 'bot_status.json'
LOG_FILE = BOT_DIR / 'bot_logs.txt'
REFRESH_INTERVAL = 3  # 秒，数据自动刷新频率

process = None
log_lines = []
dashboard_data = {
    'gold': 0,
    'gold_gain': 0,
    'level': 1,
    'exp_gain': 0,
    'steal_today': 0,
    'harvest_today': 0,
    'nickname': '未知',
    'qq_id': '未知',
    'start_time': None,
    'is_background_running': False,
}
stats = defaultdict(int)
level_to_exp = {}

# 加载经验表
role_json = BOT_DIR / 'gameConfig' / 'RoleLevel.json'
if role_json.exists():
    try:
        with open(role_json, 'r', encoding='utf-8') as f:
            data = json.load(f)
            level_to_exp = {int(k): v.get('needExp', 100) for k, v in data.items()}
    except:
        pass

# ====================== 数据持久化 ======================
def load_status():
    if STATUS_FILE.exists():
        try:
            data = json.loads(STATUS_FILE.read_text(encoding='utf-8'))
            dashboard_data.update(data)
            if 'start_time' in data and data['start_time']:
                dashboard_data['start_time'] = float(data['start_time'])
            print("[加载] 从 bot_status.json 恢复累计数据和运行时间")
            return True
        except Exception as e:
            print("[加载失败]", e)
    return False


def save_status():
    data = {
        'gold': dashboard_data['gold'],
        'gold_gain': dashboard_data['gold_gain'],
        'level': dashboard_data['level'],
        'exp_gain': dashboard_data['exp_gain'],
        'steal_today': dashboard_data['steal_today'],
        'harvest_today': dashboard_data['harvest_today'],
        'nickname': dashboard_data['nickname'],
        'qq_id': dashboard_data['qq_id'],
        'start_time': dashboard_data['start_time'] if dashboard_data['start_time'] else None,
    }
    STATUS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def reset_cumulative():
    dashboard_data.update({
        'gold_gain': 0,
        'exp_gain': 0,
        'steal_today': 0,
        'harvest_today': 0,
    })
    if STATUS_FILE.exists():
        STATUS_FILE.unlink()
    ui.notify('累计数据已重置（后台挂机继续运行）', type='positive')
    refresh_ui()


# ====================== 日志持久化 ======================
def append_log(line: str):
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def load_historical_logs():
    global log_lines
    log_lines = []
    if LOG_FILE.exists():
        try:
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                log_lines = [line.strip() for line in lines[-500:] if line.strip()]
            print(f"[加载] 从 bot_logs.txt 恢复 {len(log_lines)} 条历史日志")
        except:
            pass


# ====================== 解析日志 ======================
def parse_line(line: str):
    line = line.strip()
    if not line:
        return

    log_lines.append(line)
    append_log(line)

    updated = False

    if '昵称:' in line:
        m = re.search(r'昵称:\s*(.+)', line)
        if m:
            dashboard_data['nickname'] = m.group(1).strip()
            updated = True

    if 'GID:' in line:
        m = re.search(r'GID:\s*(\d+)', line)
        if m:
            dashboard_data['qq_id'] = m.group(1)
            updated = True

    if '等级:' in line:
        m = re.search(r'等级:\s*(\d+)', line)
        if m:
            lv = int(m.group(1))
            dashboard_data['level'] = lv
            updated = True

    if '金币:' in line:
        m = re.search(r'金币:\s*([\d,]+)', line)
        if m:
            val = int(m.group(1).replace(',', ''))
            dashboard_data['gold'] = val
            updated = True

    if m := re.search(r'花费\s*(\d+)\s*金币', line):
        cost = int(m.group(1))
        dashboard_data['gold'] -= cost
        dashboard_data['gold_gain'] -= cost
        updated = True

    if m := re.search(r'偷(\d+)', line):
        count = int(m.group(1))
        dashboard_data['steal_today'] += count
        stats['steal_count'] += count
        updated = True

    if m := re.search(r'(?:收获|收):?\s*(\d+)', line):
        count = int(m.group(1))
        dashboard_data['harvest_today'] += count
        stats['harvest_count'] += count
        exp_add = count * 2
        dashboard_data['exp_gain'] += exp_add
        updated = True

    if updated:
        save_status()


# ====================== 刷新函数 ======================
def refresh_ui():
    is_running = dashboard_data['is_background_running'] or (process and process.poll() is None)

    if is_running and dashboard_data['start_time']:
        sec = time.time() - dashboard_data['start_time']
        uptime_str = time.strftime('%H:%M:%S', time.gmtime(sec))
    else:
        uptime_str = '--:--:--'

    status.text = f"{'运行中 ' + uptime_str if is_running else '已停止'}"

    gold_label.text = f"{dashboard_data['gold']:,}"
    level_label.text = f"Lv.{dashboard_data['level']}"
    steal_label.text = str(dashboard_data['steal_today'])
    harvest_label.text = str(dashboard_data['harvest_today'])
    exp_gain_label.text = f"+{dashboard_data['exp_gain']:,}"

    user_info_label.text = f"昵称: {dashboard_data['nickname']} | QQ: {dashboard_data['qq_id']} | 等级: Lv.{dashboard_data['level']}"


def refresh_analysis():
    if not dashboard_data['start_time']:
        analysis_table.rows = []
        return

    sec = time.time() - dashboard_data['start_time']
    hours = max(0.01, sec / 3600)

    rows = [
        {'指标': '运行时间',       '值': time.strftime('%H:%M:%S', time.gmtime(sec)),     '单位/说明': ''},
        {'指标': '净金币变化',     '值': f"{dashboard_data['gold_gain']:,}",             '单位/说明': '（收入-支出）'},
        {'指标': '平均每小时金币', '值': f"{int(dashboard_data['gold_gain'] / hours):,}",'单位/说明': '金币/h'},
        {'指标': '累计偷菜次数',   '值': stats['steal_count'],                           '单位/说明': '次'},
        {'指标': '累计收获次数',   '值': stats['harvest_count'],                        '单位/说明': '次'},
        {'指标': '累计经验增加',   '值': f"{dashboard_data['exp_gain']:,}",             '单位/说明': '经验'},
        {'指标': '平均每小时经验', '值': f"{int(dashboard_data['exp_gain'] / hours):,}", '单位/说明': '经验/h'},
    ]
    analysis_table.rows = rows


# ====================== 自动刷新（每3秒读取文件） ======================
def read_latest_data():
    load_status()
    load_historical_logs()
    refresh_ui()
    refresh_analysis()


# ====================== 启动/停止 ======================
def start_bot():
    global process

    load_status()
    load_historical_logs()

    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            dashboard_data['is_background_running'] = True
            ui.notify('检测到后台挂机进程，已恢复累计数据和历史日志', type='positive')
            refresh_ui()
            return
        except:
            PID_FILE.unlink()

    code = code_input.value.strip()
    if not code:
        ui.notify('请填写 --code', type='negative')
        return

    cmd = [NODE_CMD, str(BOT_DIR / MAIN_SCRIPT), '--code', code]
    if interval_input.value:
        cmd += ['--interval', str(int(interval_input.value))]
    if friend_interval_input.value:
        cmd += ['--friend-interval', str(int(friend_interval_input.value))]

    try:
        process = subprocess.Popen(
            cmd,
            cwd=str(BOT_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace',
            bufsize=1,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0,
            start_new_session=True
        )

        PID_FILE.write_text(str(process.pid))
        dashboard_data['is_background_running'] = True

        def reader():
            dashboard_data['start_time'] = time.time()
            stats.clear()
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line.strip():
                    parse_line(line)
            if PID_FILE.exists():
                PID_FILE.unlink()
            dashboard_data['is_background_running'] = False
            ui.notify('后台挂机进程已退出', type='info')

        threading.Thread(target=reader, daemon=True).start()
        refresh_ui()
        ui.notify('挂机已启动（浏览器关闭也不会停止）', type='positive')

    except Exception as e:
        ui.notify(f'启动失败：{str(e)}', type='negative')


def stop_bot(force=False):
    global process

    stopped = False

    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            if os.name == 'nt':
                os.system(f'taskkill /PID {pid} /F /T')
            else:
                os.killpg(os.getpgid(pid), signal.SIGTERM)
                time.sleep(1)
                try:
                    os.killpg(os.getpgid(pid), signal.SIGKILL)
                except:
                    pass
            stopped = True
            ui.notify('后台挂机已停止', type='positive')
        except Exception as e:
            ui.notify(f'停止失败：{str(e)}（可能需要管理员权限）', type='warning')
        finally:
            if PID_FILE.exists():
                PID_FILE.unlink()

    if not stopped:
        ui.notify('没有检测到后台挂机进程', type='info')

    dashboard_data['start_time'] = None
    dashboard_data['is_background_running'] = False
    if STATUS_FILE.exists():
        STATUS_FILE.unlink()
    if LOG_FILE.exists():
        LOG_FILE.unlink()
    log_lines.clear()
    refresh_ui()


# ====================== UI ======================
with ui.header(elevated=True).classes('bg-gradient-to-r from-indigo-950 to-purple-950 text-white justify-center'):
    ui.label('QQ农场经典挂机控制台').classes('text-3xl font-bold tracking-wider')

with ui.column().classes('items-center gap-6 q-mt-lg q-mb-xl w-full max-w-4xl mx-auto px-4'):
    with ui.row().classes('justify-center items-center gap-6 flex-wrap w-full'):
        code_input = ui.input(
            label='登录Code',
            placeholder='从抓包或登录态获取',
            validation={'不能为空': lambda v: v and v.strip()}
        ).props('outlined dense clearable rounded bordered').classes('min-w-72 flex-1 max-w-xs')

        interval_input = ui.number(
            label='自家间隔(秒)',
            value=30,
            min=5,
            step=5
        ).props('outlined dense rounded bordered').classes('w-36')

        friend_interval_input = ui.number(
            label='好友间隔(秒)',
            value=60,
            min=5,
            step=30
        ).props('outlined dense rounded bordered').classes('w-36')

with ui.row().classes('justify-center gap-6 q-mb-10 w-full max-w-4xl mx-auto px-4 flex-wrap'):
    ui.button('开始挂机', on_click=start_bot, color='green', icon='play_arrow')\
      .props('push unelevated rounded-lg padding="md lg"')\
      .classes('text-lg font-medium shadow-lg hover:scale-105 transition-transform min-w-40')

    ui.button('停止挂机', on_click=stop_bot, color='red', icon='stop')\
      .props('push unelevated rounded-lg padding="md lg"')\
      .classes('text-lg font-medium shadow-lg hover:scale-105 transition-transform min-w-40')

    ui.button('强制终止', on_click=lambda: stop_bot(True), color='negative', icon='power_settings_new')\
      .props('flat rounded-lg padding="md lg"')\
      .classes('text-lg min-w-40')

    ui.button('重置累计数据', on_click=reset_cumulative, color='orange', icon='refresh')\
      .props('push unelevated rounded-lg padding="md lg"')\
      .classes('text-lg font-medium shadow-lg hover:scale-105 transition-transform min-w-40 bg-orange-700 text-white')

with ui.column().classes('items-center q-mb-10 w-full max-w-4xl mx-auto px-4'):
    status = ui.label('状态：已停止').classes(
        'text-xl font-bold text-center tracking-wider '
        'text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-blue-400'
    )

    user_info_label = ui.label('昵称: 未登录 | QQ: 未登录 | 等级: 未登录').classes(
        'text-lg text-center text-cyan-300'
    )

with ui.tabs() as tabs:
    tab_dashboard = ui.tab('仪表盘')
    tab_analysis  = ui.tab('收益分析')
    tab_log       = ui.tab('控制台日志')

with ui.tab_panels(tabs, value=tab_dashboard).classes('w-full bg-transparent'):
    with ui.tab_panel(tab_dashboard):
        with ui.row().classes('justify-center items-center wrap gap-8 q-pa-lg max-w-5xl mx-auto'):
            with ui.card().classes('bg-gradient-to-br from-blue-950/80 to-indigo-950/60 backdrop-blur-md border border-blue-800/40 rounded-2xl shadow-2xl w-72 hover:shadow-cyan-500/30 transition-shadow text-center'):
                ui.label('当前金币').classes('text-base opacity-80 tracking-wide')
                gold_label = ui.label('0').classes('text-5xl font-black text-cyan-300 mt-2')

            with ui.card().classes('bg-gradient-to-br from-purple-950/80 to-indigo-950/60 backdrop-blur-md border border-purple-800/40 rounded-2xl shadow-2xl w-72 hover:shadow-purple-500/30 transition-shadow text-center'):
                ui.label('当前等级').classes('text-base opacity-80 tracking-wide')
                level_label = ui.label('Lv.1').classes('text-5xl font-black text-purple-300 mt-2')

            with ui.card().classes('bg-gradient-to-br from-green-950/80 to-emerald-950/60 backdrop-blur-md border border-green-800/40 rounded-2xl shadow-2xl w-72 hover:shadow-green-500/30 transition-shadow text-center'):
                ui.label('今日偷菜').classes('text-base opacity-80 tracking-wide')
                steal_label = ui.label('0').classes('text-5xl font-black text-green-300 mt-2')

            with ui.card().classes('bg-gradient-to-br from-teal-950/80 to-cyan-950/60 backdrop-blur-md border border-teal-800/40 rounded-2xl shadow-2xl w-72 hover:shadow-teal-500/30 transition-shadow text-center'):
                ui.label('今日收获').classes('text-base opacity-80 tracking-wide')
                harvest_label = ui.label('0').classes('text-5xl font-black text-teal-300 mt-2')

            with ui.card().classes('bg-gradient-to-br from-amber-950/80 to-yellow-950/60 backdrop-blur-md border border-amber-800/40 rounded-2xl shadow-2xl w-72 hover:shadow-yellow-500/30 transition-shadow text-center'):
                ui.label('经验增加值').classes('text-base opacity-80 tracking-wide')
                exp_gain_label = ui.label('+0').classes('text-5xl font-black text-yellow-300 mt-2')

    with ui.tab_panel(tab_analysis):
        analysis_table = ui.table(
            columns=[
                {'name': '指标', 'label': '指标', 'field': '指标', 'align': 'left'},
                {'name': '值',   'label': '值',   'field': '值',   'align': 'right'},
                {'name': '单位/说明', 'label': '单位/说明', 'field': '单位/说明', 'align': 'left'}
            ],
            rows=[],
            row_key='指标',
            pagination={'rowsPerPage': 15}
        ).props('dense bordered separator-cell').classes('w-full text-body1 bg-transparent text-slate-200 mx-auto max-w-5xl')

    with ui.tab_panel(tab_log):
        with ui.card().classes('w-full max-w-5xl mx-auto bg-black/80 backdrop-blur-md border border-slate-700/50 rounded-2xl shadow-inner overflow-hidden'):
            log_container = ui.column().classes('w-full h-96 p-5 font-mono text-base leading-relaxed overflow-y-auto scrollbar-thin scrollbar-thumb-cyan-600')

            def update_log():
                log_container.clear()
                with log_container:
                    for line in log_lines:
                        color = 'text-lime-300'
                        if any(kw in line for kw in ['成功', '收获', '种植', '浇水', '施肥']):
                            color = 'text-green-400 font-medium'
                        elif any(kw in line for kw in ['偷', '偷到', '偷菜']):
                            color = 'text-violet-400 font-medium'
                        elif any(kw in line for kw in ['失败', '错误', '断开', '异常']):
                            color = 'text-red-400 font-medium'
                        elif '购买' in line or '花费' in line:
                            color = 'text-amber-400'
                        ui.label(line).classes(f'{color} whitespace-pre-wrap break-words')

            ui.timer(1.0, update_log)

ui.label('提示：经验增加值基于 1白萝卜 = +2经验 计算，如作物变化请告知调整').classes('text-center text-sm opacity-60 q-mt-6 q-mb-4')

# 页面加载时恢复
load_status()
load_historical_logs()
refresh_ui()
refresh_analysis()

# 每3秒自动从文件读取刷新（解决不同步问题）
ui.timer(3.0, read_latest_data)


ui.run(title='QQ农场经典挂机控制台', dark=True, port=8080, reload=False)
