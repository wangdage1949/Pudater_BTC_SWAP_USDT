from telethon import TelegramClient
import asyncio

# # 请替换为你的API ID和Hash  申请地址： https://my.telegram.org/auth
api_id = '266666'
api_hash = 'd55656565656'
phone_number = '+86133333333333333'
async def main():
    client = TelegramClient('session', api_id, api_hash)
    await client.start(phone=phone_number)

    print("正在获取对话列表...")
    async for dialog in client.iter_dialogs():
        print(f"ID: {dialog.id}, 名称: {dialog.name}, 类型: {dialog.is_group}")
        if "普达特量化交易信号" in dialog.name:
            print(f"找到目标群组! ID: {dialog.id}")

    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())