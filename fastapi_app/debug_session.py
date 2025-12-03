import asyncio
from core.session_store import SessionStore

async def check():
    store = SessionStore('redis://redis:6379')
    await store.connect()
    session = await store.get_session('ac659c44-e8fd-4645-bf05-010a3129990f')
    if session:
        print(f'Status: {session.status}')
        print(f'last_ai_message: {session.last_ai_message}')
        print(f'Messages count: {len(session.messages)}')
        if session.messages:
            print(f'Last message: {session.messages[-1]}')
    else:
        print('Session not found')
    await store.disconnect()

asyncio.run(check())
