# start.py - 完整版：标题改为“QQ农场经典挂机控制台”并居中，所有选项卡内容居中

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

# ====================== 配置 ======================
BOT_DIR = Path('.')  # start.py 放在 qq-farm-bot 根目录下
NODE_CMD = 'node'
MAIN_SCRIPT = 'client.js'

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

# ====================== 解析日志 ======================
def parse_line(line: str):
    line = line.strip()
    if not line:
        return

    log_lines.append(line)

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
        refresh_ui()


def refresh_ui():
    if dashboard_data['start_time']:
        sec = time.time() - dashboard_data['start_time']
        uptime_str = time.strftime('%H:%M:%S', time.gmtime(sec))
    else:
        uptime_str = '--:--:--'

    status.text = f"{'运行中 ' + uptime_str if process and process.poll() is None else '已停止'}"

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


# ====================== 启动/停止 ======================
def start_bot():
    global process
    if process and process.poll() is None:
        ui.notify('已有进程在运行', type='warning')
        return

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
            bufsize=1
        )

        def reader():
            dashboard_data['start_time'] = time.time()
            stats.clear()
            dashboard_data['exp_gain'] = 0
            dashboard_data['gold_gain'] = 0
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line.strip():
                    parse_line(line)
            ui.notify('进程已退出', type='info')

        threading.Thread(target=reader, daemon=True).start()
        refresh_ui()

    except Exception as e:
        ui.notify(f'启动失败：{str(e)}', type='negative')


def stop_bot(force=False):
    global process
    if not process or process.poll() is not None:
        ui.notify('没有运行中的进程', type='info')
        return

    try:
        sig = signal.CTRL_C_EVENT if os.name == 'nt' else signal.SIGINT
        process.send_signal(sig)
        time.sleep(1.8 if force else 0.8)
        if process.poll() is None:
            process.kill()
    except:
        pass

    dashboard_data['start_time'] = None
    refresh_ui()
    ui.notify('已停止' if not force else '强制终止', type='warning')


# ====================== UI ======================
# 标题 - 居中 + 更大字体
with ui.header(elevated=True).classes('bg-gradient-to-r from-indigo-950 to-purple-950 text-white justify-center'):
    ui.label('QQ经典农场挂机控制台').classes('text-3xl font-bold tracking-wider')

# 登录输入区 - 居中
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
            min=10,
            step=5
        ).props('outlined dense rounded bordered').classes('w-36')

        friend_interval_input = ui.number(
            label='好友间隔(秒)',
            value=180,
            min=60,
            step=30
        ).props('outlined dense rounded bordered').classes('w-36')

# 开始/停止按钮区 - 居中
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

# 状态 + 登录信息 - 居中
with ui.column().classes('items-center q-mb-10 w-full max-w-4xl mx-auto px-4'):
    status = ui.label('状态：已停止').classes(
        'text-xl font-bold text-center tracking-wider '
        'text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-blue-400'
    )

    user_info_label = ui.label('昵称: 未登录 | id: 未登录 | 等级: 未登录').classes(
        'text-lg text-center text-cyan-300'
    )

# 选项卡区 - 标签居中，内容居中
with ui.tabs().classes('w-full max-w-4xl mx-auto justify-center') as tabs:
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
                    for line in log_lines[-500:]:
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

ui.timer(1.5, refresh_ui)
ui.timer(5.0, refresh_analysis)

ui.run(title='QQ农场经典挂机控制台', dark=True, port=8080, reload=False)