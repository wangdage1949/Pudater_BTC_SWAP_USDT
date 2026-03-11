from telethon import TelegramClient
import asyncio

# 请替换为你的API ID和Hash
api_id = '266666'
api_hash = 'd55656565656'
phone_number = '+86133333333333333'

async def main():
    client = TelegramClient('session', api_id, api_hash)
    await client.start(phone=phone_number)

    print("正在获取对话列表...")
    # 定义需要查找的群名称关键词（可根据需要修改）
    target_names = ["普达特量化交易", "返回信号", "测试信号"]

    async for dialog in client.iter_dialogs():
        print(f"ID: {dialog.id}, 名称: {dialog.name}, 类型: {dialog.is_group}")
        for target in target_names:
            if target in dialog.name:  # 如果群名包含关键词
                print(f"✅ 找到目标群组! 名称关键词: '{target}', 实际群名: {dialog.name}, ID: {dialog.id}")

    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
