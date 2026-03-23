"""
--------王大哥信号群跟单机器人-----
跟单要求：
1、关注我的推特 https://x.com/hhltz8848
2、使用我的邀请码注册欧意 https://okx.com/join/47586405  （必须）
我能为你做的：
1.免费协助你在本地电脑上安装跟单机器人 （可以远程协助安装）
-----------------------------
POWER By 王大哥 Telegrame: wangdage1949
需要安装的库 pip install asyncio telethon ccxt nest_asyncio pytz python-okx
"""


import asyncio
import time
from telethon import TelegramClient, events
import re
from datetime import datetime, timezone, timedelta
import nest_asyncio
import logging
import pytz
import contextvars
import subprocess
import threading
from okx.Account import AccountAPI
from okx.Trade import TradeAPI
from okx.MarketData import MarketAPI
import requests


# 把 telethon 自己的日志关小声 / 静音
telethon_logger = logging.getLogger('telethon')
telethon_logger.setLevel(logging.CRITICAL)   # 想完全不看就用 CRITICAL

# 保险一点，把网络层相关的也压下去
logging.getLogger('telethon.network').setLevel(logging.CRITICAL)
logging.getLogger('telethon.client').setLevel(logging.CRITICAL)

# 配置异步支持
nest_asyncio.apply()

#----------------------API配置部分---------------------------------

# Telegram 配置 https://my.telegram.org/auth
api_id = '323232323'
api_hash = 'd7f4020202020202'
phone_number = '+8613838383388'

#返回消息机器人申请：https://teleme.io/articles/create_your_own_telegram_bot?hl=zh-hans
GROUP_IDS = [-0003744731100,-00000000000] # 接收信号（第二个群组为自己新建的群组，用于测试和发送指令）
CHANNEL_ID = -1000000000000      # 返回信号到指定群组 （可以单独开发 钉钉机器人群组）
#----------------------实盘模拟盘切换---------------------------------
api_key = '2222'
secret_key = '22222'
passphrase = '22222'
flag = '0'  # 0 实盘，1 模拟盘
leverage = 10 #默认1倍  解释（ 0.1BTC * 10 = 1张 ）
bucang = 2 # 开启偷鸡功能后，默认补仓张数

#---------------------- 初始化客户端 ---------------------------------
#accountAPI = AccountAPI(api_key, secret_key, passphrase, True, flag)
accountAPI = AccountAPI(api_key, secret_key, passphrase, False, flag)
trade_api = TradeAPI(api_key, secret_key, passphrase, False, flag)
market_client  = MarketAPI(api_key, secret_key, passphrase, False, flag)

#--------------------------------- 全局变量 ---------------------------------
def utc_now():
    return datetime.now(timezone.utc)
symbol = 'BTC-USDT-SWAP'  # 定义交易对
paused = False   #机器人暂停
start_time = utc_now()  # 启动时间（UTC aware）
initial_balance = None  #初始化余额
last_open_price = None  #最后一次开仓价
trade_profit = 0   #盈利情况
conservative_mode = False  #偷鸡开关标识）
long_positions = []  # 存储多单记录
short_positions = []  # 存储空单记录
monitoring_task = None  # 实时监控任务
MAX_RETRIES = 5  # 多单市场监控任务最大重试次数、防止卡死，卡死后不做任何动作，优先监听信号
RETRY_DELAY = 2  # 多单市场监控任务每次重试的间隔（秒）、防止卡死，卡死后不做任何动作，优先监听信号
MAX_RETRIES_KONG = 5  # 空单市场监控任务最大重试次数（空单监控）
RETRY_DELAY_KONG = 2  # 空单市场监控任务每次重试的间隔（秒）（空单监控）
CONTROL_COMMANDS = ["暂停", "重启", "开启偷鸡", "关闭偷鸡", "运行时间"]  #机器人支持的命令
china_timezone = pytz.timezone('Asia/Shanghai')  #北京时间
client = None  # 初始化全局 client 变量，用于发送消息
monitoring_long_positions = False  # 多单监控任务标志
monitoring_short_positions = False  # 空单监控任务标志
lock = threading.Lock() #减仓仓位锁
long_lots = 0 # 累计开多张数
short_lots = 0 # 累计开空张数




# OKX 对时间
def okx_time_offset_seconds():
    r = requests.get("https://www.okx.com/api/v5/public/time", timeout=5)
    r.raise_for_status()
    server_ms = int(r.json()["data"][0]["ts"])
    local_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    # server - local
    diff = (server_ms - local_ms) / 1000.0
    # 留一点“不要超前”的安全边际，避免变成未来时间
    return diff - 0.2

OFFSET_SEC = okx_time_offset_seconds()
print(f"[OKX补偿] 使用偏移 {OFFSET_SEC:.3f}s")

# ---- python-okx 的时间戳函数（延迟不得大于3MS）----
import okx.utils as okx_utils

def patched_get_timestamp():
    t = datetime.now(timezone.utc) + timedelta(seconds=OFFSET_SEC)
    return t.isoformat(timespec="milliseconds").replace("+00:00", "Z")

okx_utils.get_timestamp = patched_get_timestamp

#----------------------日志部分---------------------------------
main_logger = logging.getLogger("main_logger")
if not main_logger.hasHandlers():
    main_logger.setLevel(logging.INFO)

    # 日志格式
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    # 保存日志到文件
    file_handler = logging.FileHandler('jijin.log', mode='a', encoding='utf-8')
    file_handler.setFormatter(formatter)
    main_logger.addHandler(file_handler)

    # 输出日志到终端
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    main_logger.addHandler(console_handler)

# 仅输出到终端
console_logger = logging.getLogger("console_logger")
if not console_logger.hasHandlers():
    console_logger.setLevel(logging.INFO)  # 控制台日志级别为INFO

    # 输出日志到终端
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(message)s'))  # 控制台只需要简单的消息
    console_logger.addHandler(console_handler)

#--------------------------------- 获取余额 ---------------------------------
def get_balance():
    try:
        balance = accountAPI.get_account_balance("USDT")
        if balance['code'] == '0' and balance['data']:
            # 取第一个账户里的 totalEq 字段（总资产估值）
            total_eq = balance['data'][0].get('totalEq')
            print(f"余额: {total_eq}")
            return float(total_eq) if total_eq else 0
        else:
            main_logger.error(f"获取余额失败: 返回数据异常 {balance}")
            return 0
    except Exception as e:
        main_logger.error(f"获取余额失败: {e}")
        return 0

#--------------------------------- 计算加权平均价格---------------------------------
def calculate_weighted_avg_price(positions, action=None):
    """
    计算加权平均价格。如果action是"减多仓"或"减空仓"，只更新数量，不计算加权价格。
    """
    # 如果是减仓操作，直接返回现有价格而不计算加权平均价格
    if action in ["减多仓", "减空仓"]:
        return None  # 可以返回其他默认值，或者保持当前价格不变

    # 过滤掉价格为 None 或已经平仓的仓位
    valid_positions = [pos for pos in positions if pos['price'] is not None and pos['quantity'] > 0]

    # 如果没有有效仓位，返回 None 或其他合适的默认值
    if not valid_positions:
        return None

    total_qty = sum(pos['quantity'] for pos in valid_positions)

    # 防止除以零
    if total_qty == 0:
        return None

    # 计算加权价格
    weighted_sum = sum(pos['price'] * pos['quantity'] for pos in valid_positions)
    return weighted_sum / total_qty

def update_position_for_partial_closure(positions, quantity_to_close, action=None):
    """
    更新仓位时，减仓并且根据动作决定是否更新价格。
    如果动作为“减多仓”或“减空仓”，则只更新数量，价格不变。
    """
    remaining_qty_to_close = quantity_to_close
    updated_positions = []

    # 使用锁保护更新仓位的代码
    with lock:
        # 更新仓位数量
        for pos in positions:
            if remaining_qty_to_close <= 0:
                updated_positions.append(pos)  # 如果减仓完成，直接加入剩余的仓位
                continue

            if pos['quantity'] > 0:
                if pos['quantity'] <= remaining_qty_to_close:
                    remaining_qty_to_close -= pos['quantity']
                    pos['quantity'] = 0  # 清空该仓位的数量
                else:
                    pos['quantity'] -= remaining_qty_to_close
                    remaining_qty_to_close = 0  # 减仓完成，退出循环

            updated_positions.append(pos)  # 更新后的仓位信息

        # 如果是“减多仓”或“减空仓”，不更新价格
        if action in ["减多仓", "减空仓"]:
            # 在这类操作下，我们假设仓位的价格信息不做改变
            pass

        # 计算更新后的仓位数量
        remaining_quantity = sum(pos['quantity'] for pos in updated_positions)

    # 返回更新后的仓位和当前剩余仓位数量
    return updated_positions, remaining_quantity


#---------------------------------外挂部分---------------------------------
# 监控多单函数
async def monitor_long_positions(symbol):
    global long_positions
    global client, conservative_mode
    retries = 0  # 重试计数器
    while retries < MAX_RETRIES:
        try:
            avg_price_long = None  # 初始化多单均价变量
            while long_positions and conservative_mode:

                # 获取实时市场价格
                ticker = market_client.get_ticker(instId=symbol)
                real_time_price = float(ticker['data'][0]['last'])

                # 更新多单信息
                avg_price_long = round(calculate_weighted_avg_price(long_positions),1)
                long_quantity = round(sum(pos['quantity'] for pos in long_positions),1)

                huoli = round(real_time_price - avg_price_long ,1)  # 多单获利
                loss_duo = round(avg_price_long - real_time_price,1) #多单亏损

                # 模拟日志输出 防止终端输出缓冲区过大
                log_message = f"当前持有多单{long_quantity}张，均价: {avg_price_long}， 实时价格: {real_time_price}, 单张获利: {huoli}"
                # 使用more命令分页显示日志
                subprocess.Popen(f'echo {log_message} | more', shell=True)

                await asyncio.sleep(0.2)  # 每轮检查歇0.2秒，确保准确的仓位


                # 平仓多单逻辑
                if long_quantity > 20 and huoli >= 140:  # 持仓大于100且获利大于等于110（保本）
                    await handle_partial_closure(symbol, long_positions, long_quantity, huoli, real_time_price, "多", 0.8)
                    await asyncio.sleep(1)  # 每轮条件满足，执行后歇1秒，防止仓位未更新多条件触发

                elif long_quantity > 10 and huoli >= 150:  # 持仓大于60且获利大于等于140
                    await handle_partial_closure(symbol, long_positions, long_quantity, huoli, real_time_price, "多", 0.8)
                    await asyncio.sleep(1)  # 每轮条件满足，执行后歇1秒，防止仓位未更新多条件触发

                elif long_quantity > 9 and huoli >= 160:  # 持仓大于40且获利大于等于180
                    await handle_partial_closure(symbol, long_positions, long_quantity, huoli, real_time_price, "多", 0.8)
                    await asyncio.sleep(1)  # 每轮条件满足，执行后歇1秒，防止仓位未更新多条件触发

                elif long_quantity > 4 and huoli >= 200:  # 持仓大于20且获利大于等于200，平仓80%
                    await handle_partial_closure(symbol, long_positions, long_quantity, huoli, real_time_price, "多", 0.8)
                    await asyncio.sleep(1)  # 每轮条件满足，执行后歇1秒，防止仓位未更新多条件触发

                #全平的函数，0张以上大于250全跑，或者盈利400以上
                elif long_quantity > 0 and huoli >= 400:  # 持仓大于0且获利大于等于500,全平
                    await handle_full_closure(symbol, long_positions, long_quantity, huoli, real_time_price, "多")
                    await asyncio.sleep(1)  # 每轮条件满足，执行后歇1秒，防止仓位未更新多条件触发

                #如果当前多单持仓小于2张，同时亏损大于500，自行补仓2张
                elif long_quantity < 2 and loss_duo >= 500:  # 持仓大于0小于3且亏损大于100
                    await handle_replenish(symbol, long_positions, real_time_price, loss_duo, "多" ,bucang)
                    await asyncio.sleep(1)  # 每轮条件满足，执行后歇1秒，防止仓位未更新多条件触发

                await asyncio.sleep(0.5)  # 让出控制权

        except Exception as e:
            main_logger.error(f"监控多单时出错: {str(e)}")
            retries += 1  # 重试次数加1
            if retries >= MAX_RETRIES:
                main_logger.error(f"监控多单任务重试失败 {MAX_RETRIES} 次，退出任务.")
                # long_positions = []  # 备用，当前尚未遇到错误
                break  # 超过最大重试次数，退出循环
            else:
                main_logger.info(f"监控多单发生异常，准备重试 {retries}/{MAX_RETRIES} 次...")
                await asyncio.sleep(RETRY_DELAY)  # 冷静2秒再重试

        await asyncio.sleep(0.5)  # 让出控制权

# 监控空单的函数
async def monitor_short_positions(symbol):
    global short_positions
    global client, conservative_mode
    attempts = 0  # 尝试计数器
    while attempts < MAX_RETRIES_KONG:
        try:
            avg_price_short = None  # 初始化空单均价变量
            while short_positions and conservative_mode:
                # 获取实时市场价格
                ticker = market_client.get_ticker(instId=symbol)
                real_time_price = float(ticker['data'][0]['last'])

                # 更新空单信息
                avg_price_short = round(calculate_weighted_avg_price(short_positions),1)
                short_quantity = round(sum(pos['quantity'] for pos in short_positions),1)
                huoli = round(avg_price_short - real_time_price, 1)  # 空单获利
                loss_kong = round(real_time_price - avg_price_short,1)  # 空单亏损

                # 模拟日志输出 防止终端输出缓冲区过大
                log_message = f"当前持有空单{short_quantity}张，均价: {avg_price_short}, 实时价格: {real_time_price}, 单张获利: {huoli}"
                # 使用more命令分页显示日志
                subprocess.Popen(f'echo {log_message} | more', shell=True)

                await asyncio.sleep(0.2)  # 每轮检查歇0.2秒，确保准确的仓位


                # 平仓空单逻辑
                #-----------------保命阶段--------------------------------------------
                if short_quantity > 20 and huoli >= 140:  # 持仓大于100且获利大于等于110
                    await handle_partial_closure(symbol, short_positions, short_quantity, huoli, real_time_price, "空", 0.8)
                    await asyncio.sleep(1)  # 每轮条件满足，执行后歇1秒，防止仓位未更新多条件触发
                elif short_quantity > 12 and huoli >= 150:  # 持仓大于60且获利大于等于140
                    await handle_partial_closure(symbol, short_positions, short_quantity, huoli, real_time_price, "空", 0.8)
                    await asyncio.sleep(1)  # 每轮条件满足，执行后歇1秒，防止仓位未更新多条件触发
                elif short_quantity > 9 and huoli >= 160:  # 持仓大于40且获利大于等于180
                    await handle_partial_closure(symbol, short_positions, short_quantity, huoli, real_time_price, "空", 0.8)
                    await asyncio.sleep(1)  # 每轮条件满足，执行后歇1秒，防止仓位未更新多条件触发
                elif short_quantity > 5 and huoli >= 200:  # 持仓大于13且获利大于等于200
                    await handle_partial_closure(symbol, short_positions, short_quantity, huoli, real_time_price, "空", 0.8)
                    await asyncio.sleep(1)  # 每轮条件满足，执行后歇1秒，防止仓位未更新多条件触发

                # 全平的函数，蚂蚁仓获利400以上全平，或者1张以上大于250全跑
                elif short_quantity > 4 and huoli >= 250:  # 持仓大于4且获利大于等于250，全平
                    await handle_full_closure(symbol, short_positions, short_quantity, huoli, real_time_price, "空")
                    await asyncio.sleep(1)  # 每轮条件满足，执行后歇1秒，防止仓位未更新多条件触发

                elif short_quantity > 0 and huoli >= 400:  # 持仓大于0且获利大于等于500，全平
                    await handle_full_closure(symbol, short_positions, short_quantity, huoli, real_time_price, "空")
                    await asyncio.sleep(1)  # 每轮条件满足，执行后歇1秒，防止仓位未更新多条件触发


                # 如果当前空单持仓小于2张，并且亏损大于500，自行补仓2张
                elif short_quantity < 2 and loss_kong >= 500:  # 持仓大于0小于3且亏损大于100,补仓
                    await handle_replenish(symbol, short_positions, real_time_price, loss_kong,"空", bucang)
                    await asyncio.sleep(1)  # 每轮条件满足，执行后歇1秒，防止仓位未更新多条件触发

                await asyncio.sleep(0.5)  # 让出控制权


        except Exception as e:
            main_logger.error(f"监控空单时出错: {str(e)}")
            attempts += 1  # 尝试次数加1
            if attempts >= MAX_RETRIES_KONG:
                main_logger.error(f"监控空单任务重试失败 {MAX_RETRIES_KONG} 次，退出任务.")
                # short_positions = []  # 备用，当前尚未遇到错误
                break  # 超过最大尝试次数，退出循环
            else:
                main_logger.info(f"监控空单发生异常，准备重试 {attempts}/{MAX_RETRIES_KONG} 次...")
                await asyncio.sleep(RETRY_DELAY_KONG)  # 冷静2秒再重试

        await asyncio.sleep(0.5)  # 让出控制权


# 辅助函数：处理部分平仓逻辑
async def handle_partial_closure(symbol, positions, quantity, huoli, real_time_price, action, fraction):
    global client

    retry_count = 0  # 初始化重试计数器
    max_retries = 2  # 最大重试次数

    while retry_count <= max_retries:
        try:
            # 计算平仓数量 保留一位小数
            total_quantity = sum(pos['quantity'] for pos in positions)
            size_half = round(total_quantity * fraction, 1)  # 要平仓的数量
            remaining_quantity = size_half
            # 更新仓位：这里假设你有一个函数用来更新仓位
            positions, remaining_quantity = update_position_for_partial_closure(positions, quantity_to_close=remaining_quantity, action=f"减{action}仓")
            # 执行平仓操作
            result = await place_order(None, symbol, f'平{action}', size_half)  # 平仓

            if result:
                main_logger.info(f"平{action}操作成功: {result['amount']} 张，当前价格: {real_time_price}")
                shengyu = quantity - size_half  # 剩余仓位数量
                # 发送Telegram消息通知
                await client.send_message(CHANNEL_ID, (
                    f"偷鸡成功:\n"
                    f"平仓方向: 平{action}\n"
                    f"部分平仓: {size_half} 张\n"
                    f"提前离场：{action}单原有持仓：{quantity} 张，单张获利: {huoli}，剩余仓位: {shengyu} 张\n"
                    f"剩余 {fraction * 100}% 等待中...\n"
                ))
                break  # 如果平仓成功，跳出重试循环

            else:
                main_logger.error(f"部分平{action}操作失败，未能成功平仓 {size_half} 张")
                await client.send_message(CHANNEL_ID, (f"部分平{action}操作失败，未能成功平仓 {size_half} 张"))
                retry_count += 1  # 增加重试次数
                if retry_count > max_retries:
                    main_logger.error(f"部分平仓重试超过最大次数({max_retries})，退出平仓操作")
                    break  # 超过最大重试次数，退出


        except Exception as e:
            # 检测特定错误信息: "You don't have any positions in this contract that can be closed."
            if 'You don\'t have any positions in this contract that can be closed.' in str(e):
                main_logger.error(f"平{action}操作失败，未找到持仓，清空对应仓位记录")

                # 清空仓位
                if action == '多':
                    long_positions = []  # 清空多单仓位记录
                    main_logger.info(f"已清空多单仓位记录: {long_positions}")
                elif action == '空':
                    short_positions = []  # 清空空单仓位记录
                    main_logger.info(f"已清空空单仓位记录: {short_positions}")

                # 发送消息到 Telegram 通道
                await client.send_message(CHANNEL_ID, (
                    f"平{action}操作失败，未找到持仓，已清空对应仓位记录。"
                ))

                break  # 清空仓位后，退出重试循环

            # 捕获异常并记录日志
            main_logger.error(f"执行部分平{action}时发生错误: {str(e)}")
            await client.send_message(CHANNEL_ID, f"部分平{action}时发生错误: {str(e)}")
            retry_count += 1  # 增加重试次数
            if retry_count > max_retries:
                main_logger.error(f"部分平仓操作错误超过最大次数({max_retries})，退出")
                break  # 超过最大重试次数，退出
            await asyncio.sleep(1)  # 出错时稍作休息，留给监听函数足够多时间的控制权

        await asyncio.sleep(1)  # 出错留出控制权



# 辅助函数：处理完全平仓逻辑
async def handle_full_closure(symbol, positions, quantity, huoli, real_time_price, action):
    global client, short_positions, long_positions
    total_quantity = sum(pos['quantity'] for pos in positions)  # 获取当前仓位的总数量
    retry_count = 0  # 初始化重试计数器
    max_retries = 2  # 最大重试次数

    while retry_count <= max_retries:
        try:
            # 完全平仓
            result = await place_order(None, symbol, f'平{action}', total_quantity)

            if result:
                main_logger.info(f"全部平{action}操作成功: {result['amount']} 张，当前价格: {real_time_price}")
                # 发送消息到 Telegram 通道
                await client.send_message(CHANNEL_ID, (
                    f"偷鸡全跑成功:\n"
                    f"平仓方向: 平{action} \n"
                    f"全部平仓: {quantity} 张 \n"
                    f"提前离场：{action}单持仓：{total_quantity} 张，单张获利{huoli}，全部跑路\n"
                ))

                # 根据动作（平多或平空），清空对应仓位信息
                if action == '多':
                    main_logger.info(f"清空多单仓位记录: {long_positions}")
                    long_positions = []  # 清空多单仓位记录
                    console_logger.info(f"平多仓操作，清空多仓记录: {long_positions}")

                elif action == '空':
                    main_logger.info(f"清空空单仓位记录: {short_positions}")
                    short_positions = []  # 清空空单仓位记录
                    console_logger.info(f"平空仓操作，清空空仓记录: {short_positions}")

                await asyncio.sleep(1)  # 给系统一些时间，避免在平仓后继续处理任务
                break  # 如果成功，跳出重试循环

            else:
                main_logger.error(f"全部平{action}操作失败，无法获取订单结果")
                retry_count += 1  # 增加重试次数
                if retry_count > max_retries:
                    main_logger.error(f"全部平仓重试超过最大次数({max_retries})，退出平仓操作")
                    # 根据动作（平多或平空），清空对应仓位信息
                    if action == '多':
                        main_logger.info(f"清空多单仓位记录: {long_positions}")
                        long_positions = []  # 清空多单仓位记录
                        console_logger.info(f"平多仓操作，清空多仓记录: {long_positions}")

                    elif action == '空':
                        main_logger.info(f"清空空单仓位记录: {short_positions}")
                        short_positions = []  # 清空空单仓位记录
                        console_logger.info(f"平空仓操作，清空空仓记录: {short_positions}")
                    break  # 超过最大重试次数，退出

        except Exception as e:
            # 检测特定错误信息: "You don't have any positions in this contract that can be closed."
            if 'You don\'t have any positions in this contract that can be closed.' in str(e):
                main_logger.error(f"{action}操作失败，未找到持仓，清空对应仓位记录")

                # 清空仓位
                if action == '多':
                    long_positions = []  # 清空多单仓位记录
                    main_logger.info(f"已清空多单仓位记录: {long_positions}")
                elif action == '空':
                    short_positions = []  # 清空空单仓位记录
                    main_logger.info(f"已清空空单仓位记录: {short_positions}")

                # 发送消息到 Telegram 通道
                await client.send_message(CHANNEL_ID, (
                    f"平{action}操作失败，未找到持仓，已清空对应仓位记录。"
                ))

                break  # 清空仓位后，退出重试循环

            # 捕获其他异常并重试
            main_logger.error(f"全部平{action}操作时出错: {str(e)}")
            retry_count += 1  # 增加重试次数
            if retry_count > max_retries:
                main_logger.error(f"全部平仓操作错误超过最大次数({max_retries})，退出")
                break  # 超过最大重试次数，退出

            await asyncio.sleep(1)  # 出错时稍作休息，避免重试过于频繁
        await asyncio.sleep(1)  # 报错，留给监听函数足够多时间的控制权


# 辅助函数：处理补仓逻辑
async def handle_replenish(symbol, positions, real_time_price, loss, action, quantity):
    global client

    retry_count = 0  # 初始化重试计数器
    max_retries = 1  # 最大重试次数

    while retry_count <= max_retries:
        try:
            # 针对多仓或空仓补仓
            if action == '多':  # 针对多仓补仓
                result = await place_order(None, symbol, f'开多', quantity)  # 补仓开单，仓位更新在开多那里

                #await asyncio.sleep(1)  # 歇1秒，等待仓位更新，防止重复下单！优先级高于平仓

            elif action == '空':  # 针对空仓补仓
                result = await place_order(None, symbol, f'开空', quantity)  # 补仓开单，仓位更新在开空那里
                #await asyncio.sleep(1)  # 歇1秒，等待仓位更新，防止重复下单！优先级高于平仓

            # 处理补仓成功后的逻辑
            if result:
                if not isinstance(loss, (int, float)) or loss < 0:
                    raise ValueError(f"无效的亏损值: {loss}")
                main_logger.info(f"补仓开{action}成功: {result['amount']} 张，当前价格: {real_time_price},当前亏损{loss}")
                await asyncio.sleep(1)  # 歇1秒，等待下单消息返回，稍后推送信息
                # 发送补仓成功消息
                await client.send_message(CHANNEL_ID, (
                    f"补仓开{action}成功:\n"
                    f"方向: 开{action}\n"
                    f"补仓数量: {quantity} 张\n"
                    f"当前亏损: {loss} / 张\n"
                    f"当前价格: {real_time_price}\n"
                ))
                break  # 如果补仓成功，跳出重试循环
            else:
                main_logger.error(f"补仓开{action}失败，未能成功下单")
                await client.send_message(CHANNEL_ID, f"补仓开{action}失败，未能成功下单。")
                retry_count += 1  # 增加重试次数
                if retry_count > max_retries:
                    main_logger.error(f"重试超过最大次数({max_retries})，退出补仓操作")
                    break  # 超过最大重试次数，退出，补仓失败就算了，保命要紧，防止重复下单。

        except Exception as e:
            # 捕获异常并记录日志
            main_logger.error(f"补仓开{action}时出错: {str(e)}")
            await client.send_message(CHANNEL_ID, (f"补仓开{action}时发生错误: {str(e)}"))
            retry_count += 1  # 增加重试次数
            if retry_count > max_retries:
                main_logger.error(f"补仓操作错误超过最大次数({max_retries})，退出")
                break  # 超过最大重试次数，退出

        await asyncio.sleep(1)  # 出错时稍作休息，防止卡死，阻碍最优先级别指令


#---------------------------------基本跟单功能---------------------------------
async def place_order(client, symbol, action, amount):
    global initial_balance, long_positions, short_positions
    global paused, monitoring_long_positions, monitoring_short_positions
    global long_lots, short_lots
    if paused:  # 检查是否处于暂停状态
        main_logger.info("当前已暂停，跳过下单")
        return None
    try:
        side, posSide = {'开多': ('buy', 'long'), '平多': ('sell', 'long'),
                         '开空': ('sell', 'short'), '平空': ('buy', 'short')}.get(action, (None, None))

        if side is None:
            main_logger.warning(f"未识别的操作: {action}")
            return None

        # 执行下单操作
        order = trade_api.place_order(
            instId=symbol,
            #tdMode="isolated", # 逐仓
            tdMode="cross",  # 全仓
            side=side,
            posSide=posSide,
            ordType="market",
            sz=str(amount)
        )

        # 检查下单是否成功
        if order.get('code') != '0':
            main_logger.error(f"下单失败: {order}")
            return None

        # 获取订单成交价格
        trade_price = order.get('price')

        if not trade_price:
            data_list = order.get('data', [])
            if not data_list:
                main_logger.error(f"下单返回的 data 为空，无法获取订单ID: {order}")
                return None

            order_id = data_list[0].get('ordId')
            if not order_id:
                main_logger.error(f"订单ID不存在: {order}")
                return None

            order_detail = trade_api.get_order(instId=symbol, ordId=order_id)
            detail_data = order_detail.get('data', [])
            if detail_data and detail_data[0].get('avgPx'):
                trade_price = float(detail_data[0]['avgPx'])
            else:
                main_logger.error(f"订单详情无成交价: {order_detail}")
                return None

        trade_price = float(trade_price)

        balance = get_balance()

        # 根据操作类型更新仓位
        if action == '开多':
            long_positions.append({'price': trade_price, 'quantity': amount})
            console_logger.info(f"记录多单开仓: {long_positions}")
        elif action == '开空':
            short_positions.append({'price': trade_price, 'quantity': amount})
            console_logger.info(f"记录空单开仓: {short_positions}")

        if initial_balance is None:
            initial_balance = balance

        balance_change = balance - initial_balance

        main_logger.info(f"下单成功: {order}")
        return {
            'timestamp': utc_now().strftime('%Y-%m-%d %H:%M:%S'),
            'action': action,
            'amount': amount,
            'current_balance': balance,
            'balance_change': balance_change,
            'trade_price': trade_price
        }

    except Exception as e:
        error_message = str(e)
        if 'You don\'t have any positions in this contract that can be closed.' in error_message:
            # 检测到错误信息，清空相关仓位并停止下单
            if '平多' in action:
                main_logger.error(f"平多操作失败，未找到持仓，清空多单仓位记录")
                long_positions.clear()
                long_lots = 0  # long_lots 被清零
                console_logger.info(f"已清空多单仓位记录: {long_positions}")
            elif '平空' in action:
                main_logger.error(f"平空操作失败，未找到持仓，清空空单仓位记录")
                short_positions.clear()
                short_lots = 0 # short_lots 被清零
                console_logger.info(f"已清空空单仓位记录: {short_positions}")

            # 发送消息到 Telegram 通道
            await client.send_message(CHANNEL_ID, (
                f"平{action}操作失败，未找到持仓，已清空对应仓位记录。"
            ))

            return None

        main_logger.error(f"下单时出错: {e}")
        return None

# 新增解析信号逻辑
def parse_new_signal(text):
    lines = text.strip().split('\n')
    if not lines:
        return None

    action = None
    symbol = "BTC-USDT-SWAP"  # 默认BTC，需要其他币种再扩展
    lots = None

    for line in lines:
        line = line.strip()

        # ========== 识别操作类型 ==========
        if "首次开多" in line or "多仓加仓" in line:
            action = "开多"
        elif "首次开空" in line or "空仓加仓" in line:
            action = "开空"
        elif "平多" in line or "多单做T" in line:
            action = "平多"
        elif "平空" in line or "空单做T" in line:
            action = "平空"

        # ========== 识别数量 ==========
        # 开仓/加仓数量
        for prefix in ["开仓数量:", "加仓数量:"]:
            if line.startswith(prefix):
                try:
                    val = line.split(":", 1)[1].strip()
                    lots = round(float(val) * leverage, 1)
                except:
                    pass

        # 平仓数量（兼容中英文冒号）
        for prefix in ["平仓数量:", "平仓数量：", "已平数量:", "已平数量："]:
            if line.startswith(prefix):
                try:
                    val = line.split(prefix[0], 1)[1].strip()
                    val = val.replace("张", "").strip()
                    lots = round(float(val) * leverage, 1)
                except:
                    pass

    if action and lots is not None:
        return action, lots, symbol

    return None


# 处理消息函数
async def handle_message(message, client):
    global leverage, paused, conservative_mode, long_positions, short_positions
    global long_lots, short_lots
    try:
        # 获取消息内容
        message_text = message.text.strip() if hasattr(message, 'text') else message.strip()
        # main_logger.info(f"收到的消息: {message_text}")

        # 如果程序已暂停，则跳过所有非控制命令的处理
        if paused and message_text not in CONTROL_COMMANDS:
            main_logger.info("当前已暂停，跳过非控制命令的处理")
            return

        # 处理控制命令
        if message_text in CONTROL_COMMANDS:
            await handle_command(message_text, client)
            return

        # 处理倍数指令（如 "8倍"）
        if re.match(r'^\s*\d+\s*倍\s*$', message_text):
            leverage = int(re.search(r'\d+', message_text).group())
            main_logger.info(f"已设置倍数为: {leverage}倍")
            await client.send_message(CHANNEL_ID, f"已设置倍数为: {leverage}倍")
            return

        # 尝试解析新格式信号
        new_signal = parse_new_signal(message_text)
        if new_signal:
            action, raw_quantity, symbol = new_signal
            main_logger.info(f"解析新格式信号: action={action}, quantity={raw_quantity}, symbol={symbol}")
            suffix = ""  # 新格式无附加信息

            # ----- 新增：处理无数量平仓 -----
            if raw_quantity is None:
                if action == "平多":
                    # 获取当前多单总持仓
                    total_qty = sum(pos['quantity'] for pos in long_positions)
                    raw_quantity = total_qty if total_qty <= 0 else long_lots  # 获取当前多单持仓数量 + 防守兜底
                    main_logger.info(f"准备平多：当前持仓量: {raw_quantity} 张")
                elif action == "平空":
                    total_qty = sum(pos['quantity'] for pos in short_positions)
                    raw_quantity = total_qty if total_qty <= 0 else short_lots # 获取当前空单持仓数量 + 防守兜底
                    main_logger.info(f"准备平空，当前持仓量: {raw_quantity} 张")
                else:
                    # 开仓信号绝对不能缺数量
                    await client.send_message(CHANNEL_ID, f"开仓信号缺少数量，无法执行: {message_text}")
                    return
                
        else:
            # 旧格式解析
            contains_laowang = "老王" in message_text
            contains_return = "返回" in message_text
            main_logger.info(f"是否包含老王: {contains_laowang}, 是否包含返回: {contains_return}")

            # 匹配旧格式信号模式
            pattern = r'^\[(开空|平空|开多|平多)\]\s*数量:(\d+\.?\d*)\s*市场:([\w-]+)\s*(返回.*|老王:.*)?$'
            match = re.match(pattern, message_text)
            if not match:
                main_logger.warning(f"未识别的指令: {message_text}")
                await client.send_message(CHANNEL_ID, f"未识别的指令: {message_text}\n请确保指令格式正确，例如：\n[开多] 数量:1 市场:BTC-USDT")
                return
            action = match.group(1)
            raw_quantity = float(match.group(2))
            symbol = match.group(3)
            suffix = match.group(4) or ""

        # ---------- 统一的数量调整逻辑（保持不变）----------
        if action in ["开多", "开空"]:
            # 开仓逻辑
            if raw_quantity == 1:
                adjusted_quantity = leverage
            elif raw_quantity == 2:
                adjusted_quantity = 2 * leverage
            elif raw_quantity == 3:
                adjusted_quantity = 3 * leverage
            elif raw_quantity == 4:
                adjusted_quantity = 4 * leverage
            elif raw_quantity == 5:
                adjusted_quantity = 5 * leverage
            elif raw_quantity == 6:
                adjusted_quantity = 6 * leverage
            elif raw_quantity == 7:
                adjusted_quantity = 7 * leverage
            elif raw_quantity == 8:
                adjusted_quantity = 8 * leverage
            else:
                adjusted_quantity = raw_quantity * leverage
            main_logger.info(f"开多/开空，监听到数量为{raw_quantity}，实际下单数量: {adjusted_quantity}")
        elif action in ["平多", "平空"]:
            # 平仓逻辑
            if raw_quantity == 1:
                adjusted_quantity = 1 * leverage
            elif raw_quantity == 2:
                adjusted_quantity = 2 * leverage
            elif raw_quantity == 3:
                adjusted_quantity = 3 * leverage
            elif raw_quantity == 4:
                adjusted_quantity = 4 * leverage
            elif raw_quantity == 5:
                adjusted_quantity = 5 * leverage
            elif raw_quantity == 6:
                adjusted_quantity = 6 * leverage
            elif raw_quantity == 7:
                adjusted_quantity = 7 * leverage
            elif raw_quantity == 8:
                adjusted_quantity = 8 * leverage
            else:
                adjusted_quantity = raw_quantity * leverage
            main_logger.info(f"平多/平空，监听到数量为{raw_quantity}，实际平仓数量: {adjusted_quantity}")
        else:
            main_logger.error(f"未知的动作: {action}")
            return

        # 调用下单函数
        result = await place_order(client, symbol, action, adjusted_quantity)
        if result:
            main_logger.info(f"下单结果: {result}")
            # 构建发送消息
            msg_parts = [
                f"下单成功:",
                f"方向: {result['action']}",
                f"数量: {result['amount']}",
                f"市场: {symbol}",
                f"余额变动: {result.get('balance_change', '未知')}"
            ]
            if suffix:  # 旧格式有附加信息才添加
                msg_parts.append(f"附加信息: {suffix}")
            await client.send_message(CHANNEL_ID, "\n".join(msg_parts))

            # 重置多单和空单的持仓
            if action == '平多':
                long_positions = []
                long_lots = 0 # 备用多单仓位数量计数清零
                main_logger.info("平多后，已重置多单持仓信息。")
            elif action == '平空':
                short_positions = []
                short_lots = 0 # 备用空单仓位计数清零
                main_logger.info("平空后，已重置空单持仓信息。")
            elif action == '开多':
                long_lots += adjusted_quantity  
                main_logger.info(f"开多张数累计:{long_lots}。")
            elif action == '开空':
                short_lots += adjusted_quantity
                main_logger.info(f"开空张数累计：{short_lots}。")
        else:
            main_logger.error(f"下单失败: action={action}, quantity={adjusted_quantity}")
            await client.send_message(CHANNEL_ID, f"下单失败: {action} {adjusted_quantity} 张")
    except Exception as e:
        main_logger.error(f"处理消息时发生错误: {e}")

# 处理控制命令
async def handle_command(command, client):
    global paused, conservative_mode
    if command == "暂停":
        paused = True
        await client.send_message(CHANNEL_ID, "已暂停交易")
        main_logger.info("已暂停交易")
    elif command == "重启":
        paused = False
        await client.send_message(CHANNEL_ID, "已重启交易")
        main_logger.info("已重启交易")
    elif command == "关闭偷鸡":
        conservative_mode = False
        await client.send_message(CHANNEL_ID, "已关闭偷鸡功能，全程跟普哥信号开平仓")
        main_logger.info("切换到正常开单模式")
    elif command == "开启偷鸡":
        conservative_mode = True
        await client.send_message(CHANNEL_ID, "已打开偷鸡功能，偷跑规则已启动")
        main_logger.info("切换到保守开单模式")
    elif command == "运行时间":
        elapsed_time = utc_now() - start_time
        current_balance = get_balance()
        balance_change = current_balance - initial_balance
        await client.send_message(
            CHANNEL_ID,
            f"机器人已运行时间: {elapsed_time}\n"
            f"初始余额: {initial_balance} USDT\n"
            f"当前余额: {current_balance} USDT\n"
            f"余额变动: {balance_change:.2f} USDT"
        )

#--------------------------------- 启动 Telegram 客户端监听---------------------------------
async def start_telegram_listener():
    global client
    async with TelegramClient('bot_session', api_id, api_hash) as client:
        # 监听新消息的事件处理器
        @client.on(events.NewMessage(chats=GROUP_IDS))
        async def message_handler(event):
            message = event.message.text
            main_logger.info(f"收到新消息: {message}")
            await handle_message(event.message, client)

        main_logger.info(f"开始监听群组: {GROUP_IDS}...")
        # 运行 Telegram 客户端事件循环
        await client.run_until_disconnected()

# 启动程序
async def main():
    global initial_balance
    initial_balance = get_balance()
    main_logger.info(f"程序启动，初始余额: {initial_balance}")
    telegram_task = asyncio.create_task(start_telegram_listener())  # 启动 Telegram 监听
    # 启动后台监控任务
    monitor_task_1 = asyncio.create_task(monitor_long_positions(symbol))  # 启动多单监控
    monitor_task_2 = asyncio.create_task(monitor_short_positions(symbol))  # 启动空单监控
    # 等待所有任务完成
    await asyncio.gather(telegram_task,monitor_task_1,monitor_task_2)

# 启动事件循环
if __name__ == '__main__':
    asyncio.run(main())  # 使用 asyncio.run() 启动事件循环

