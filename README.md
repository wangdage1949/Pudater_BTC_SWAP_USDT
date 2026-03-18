# V1.0.3更新说明

1.修复了普达特平仓信号，新增 Close Lot 参数的识别功能（重要）

    ”def parse_new_signal(text):
    lines = text.strip().split('\n')
    if not lines:
        return None

    if not lines[0].startswith('Fast Version'):
        return None

    action = None
    symbol = None
    lots = None
    close_lot = None  # 新增变量

    for line in lines:
        line = line.strip()
        if line.startswith('[Open Sell]'):
            action = "开空"
        elif line.startswith('[Close Sell]'):
            action = "平空"
        elif line.startswith('[Open Buy]'):
            action = "开多"
        elif line.startswith('[Close Buy]'):
            action = "平多"
        elif line.startswith('Symbol:'):
            base = line.split(':', 1)[1].strip()
            if base.endswith('-USDT-SWAP'):
                symbol = base
            else:
                symbol = f"{base}-USDT-SWAP"
        elif line.startswith('Lots:'):
            try:
                lots = float(line.split(':', 1)[1].strip())
                lots = round(lots * leverage, 1)
            except ValueError:
                pass
        elif line.startswith('Close Lot:'):  # 新增解析
            try:
                close_lot = float(line.split(':', 1)[1].strip())
                close_lot = round(close_lot * leverage, 1)
            except ValueError:
                pass

    if action and symbol is not None:
        # 如果是平仓，优先使用close_lot；否则使用lots→Lots若为None,则直接利用okx库获取当前持仓或者保底的long_lots/short_lots
        if action in ("平多", "平空"):
            if close_lot is not None:
                lots = close_lot
            # 如果close_lot为None，保持原有lots（可能为None）
        return action, lots, symbol
    return None
    
    “

# V1.0.2更新说明

1.修复了全部平仓无LOTS返回的窘境（重要）

       “ if new_signal:
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
                    return ”

2.修改了跟单倍数策略,此处默认开仓单位为张数，不是BTC，请确认！！！


普哥信号0.1 单位： BTC 对应信号转换 ---------- 0.1 * leverage（默认10） = 1 单位：张，请根据实际保证金自行调整。

# Pudater_BTC_SWAP_USDT

普达特量化交易激进版跟单机器人系统要求

windows/linux/ubuntu

(本地计算机均可）

对互联网传输要求极其严厉，使用前先 ping okx.com 和 ping telegrame.org ，若延时大于3MS，建议更换服务器。

---------------------------------------------------------------------------------------------------
一、安装 python 3.11 及以上版本

你能用到的库

“安装命令

pip install asyncio telethon nest_asyncio pytz python-okx 

ccxt 库已取消
”


---------------------------------------------------------------------------------------------------
二、新建立两个群组，群组名称分别为：返回信号的群，测试信号的群，获取群组的ID后，可随意更改群组名称。

运行 python waigua_群组ID获取.py （建议修改为纯英文名称）

你将会得到3个需要的群组ID，一个是普哥的信号群组ID（激进版或者稳健版），一个是测试信号的群组ID，一个是返回信号的群组ID。

# 注意你首先必须加入普达特量化交易信号群
---------------------------------------------------------------------------------------------------
三、 修改三处即可上线

1、Telegrame 对应的 API (自己申请不了就别费劲了，去闲鱼找人弄）

2、跟单群组ID和测试群组ID和返回信号的群组ID

3、OKX的实盘/模拟盘 API

最后，把  waigua_官方库_默认偷鸡功能关闭-激进版本.py  修改名称为 waigua.py 

双击执行目录中的 qidong.bat 即可上线。


修改示例

<img width="1123" height="373" alt="image" src="https://github.com/user-attachments/assets/ddb95aff-e91e-4904-9191-595fbebea045" />
---------------------------------------------------------------------------------------------------

项目关键展示

你可以向 测试消息的群组发送的指令有这么多

["暂停", "重启", "开启偷鸡", "关闭偷鸡", "运行时间"] 

<img width="553" height="167" alt="image" src="https://github.com/user-attachments/assets/c3b2ae2a-28ac-47bf-a8c3-9114a24c049c" />

<img width="554" height="127" alt="image" src="https://github.com/user-attachments/assets/09a7c0c9-b914-41f2-8486-761232432409" />

<img width="554" height="87" alt="image" src="https://github.com/user-attachments/assets/d45f5afe-3ef3-411b-9d8f-5d047eb84a49" />

<img width="553" height="92" alt="image" src="https://github.com/user-attachments/assets/8090b693-febe-484d-b8d1-75dc6f1029c4" />

async def monitor_short_positions(symbol): 空单外挂监控函数（异步）

async def monitor_long_positions(symbol):  多单外挂监控函数（异步）

<img width="553" height="309" alt="image" src="https://github.com/user-attachments/assets/15c8e640-b4ff-4b7c-9c6e-eb5e6abcc76e" />

async def handle_message(message, client): 监听函数：自行修改实际开仓平仓张数设定

本函数已加固了特殊场景（双向持仓偷鸡功能）

<img width="554" height="458" alt="image" src="https://github.com/user-attachments/assets/4724b894-04d3-4084-bad7-b1853415b1bb" />

<img width="554" height="337" alt="image" src="https://github.com/user-attachments/assets/75b5c1a5-f24c-4ae8-be66-348f7fb803b8" />

<img width="554" height="276" alt="image" src="https://github.com/user-attachments/assets/0771f2fd-47ea-4307-af91-17a3080fbab4" />

<img width="554" height="188" alt="image" src="https://github.com/user-attachments/assets/367b5095-9a80-4534-abef-690ec2e2c9b7" />

<img width="554" height="396" alt="image" src="https://github.com/user-attachments/assets/d79aacd2-5d52-4328-82d3-dbc619a8d64e" />

<img width="554" height="497" alt="image" src="https://github.com/user-attachments/assets/bc8407b7-0c85-4263-8c61-e58f29e06361" />

<img width="554" height="410" alt="image" src="https://github.com/user-attachments/assets/d2b3d1c1-7a66-4a99-8d49-7936967ac316" />

普哥狗狗打赏地址：DKPxQLwCHAPAkUQZazYKaibwWifhXnAFCd

王大哥狗狗币打赏地址：

<img width="544" height="698" alt="image" src="https://github.com/user-attachments/assets/616223e5-5e7c-4065-8767-0734502f8da5" />

最后，希望能获得您对我的关注 ：https://x.com/hhltz8848
