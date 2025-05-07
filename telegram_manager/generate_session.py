import os
import asyncio
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

async def main():
    phone_number = input("Enter your phone number (with country code): ")
    app_id = int(input("Enter your Telegram API ID: "))
    app_hash = input("Enter your Telegram API Hash: ")

    session_dir = "session_files"
    os.makedirs(session_dir, exist_ok=True)
    session_file_path = os.path.join(session_dir, f"{phone_number}.session")

    client = TelegramClient(session_file_path, app_id, app_hash)

    await client.connect()
    if not await client.is_user_authorized():
        try:
            await client.send_code_request(phone_number)
            code = input("Enter the code you received: ")
            try:
                await client.sign_in(phone_number, code)
            except SessionPasswordNeededError:
                password = input("Two-step verification enabled. Please enter your password: ")
                await client.sign_in(password=password)
        except Exception as e:
            print(f"Failed to sign in: {e}")
            await client.disconnect()
            return

    print(f"Session file generated at: {session_file_path}")
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
