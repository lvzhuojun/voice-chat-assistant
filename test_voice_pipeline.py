# -*- coding: utf-8 -*-
"""Test full voice chat pipeline: WebSocket text -> LLM -> TTS"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import asyncio, json, httpx, websockets

sys.path.insert(0, '.')

BASE = 'http://127.0.0.1:8000'
WS_BASE = 'ws://127.0.0.1:8000'

def run():
    c = httpx.Client(base_url=BASE, timeout=15)
    r = c.post('/api/auth/login', json={'email': 'lzj2729033776@gmail.com', 'password': 'TestVoice1'})
    print(f'Login: {r.status_code}')
    d = r.json()
    token = d['access_token']
    print(f'User: {d["user"]["username"]} id={d["user"]["id"]}')

    voices = c.get('/api/voices', headers={'Authorization': f'Bearer {token}'}).json()
    print(f'Voices: {[(v["id"], v["voice_name"]) for v in voices]}')

    if not voices:
        print('[FAIL] No voice models found!')
        c.close()
        return

    # Select voice
    v0 = voices[0]
    c.post(f'/api/voices/{v0["id"]}/select', headers={'Authorization': f'Bearer {token}'})
    print(f'Selected voice: {v0["voice_name"]}')

    # Create conversation
    r = c.post('/api/conversations', json={'title': 'Full pipeline test'},
               headers={'Authorization': f'Bearer {token}'})
    conv_id = r.json()['id']
    print(f'conv_id={conv_id}')
    c.close()

    asyncio.run(ws_test(token, conv_id))

    # Verify DB persistence
    c2 = httpx.Client(base_url=BASE, timeout=10)
    t2 = c2.post('/api/auth/login',
                 json={'email': 'lzj2729033776@gmail.com', 'password': 'TestVoice1'}).json()['access_token']
    msgs_db = c2.get(f'/api/conversations/{conv_id}/messages',
                     headers={'Authorization': f'Bearer {t2}'}).json()
    print(f'\nDB messages count: {len(msgs_db)}')
    for m in msgs_db:
        print(f'  [{m["role"]}] {m["content"][:60]}')
    if len(msgs_db) == 2:
        print('[OK] User + assistant messages persisted')
    elif len(msgs_db) == 1:
        print('[WARN] Only user message persisted (TTS may have failed)')
    else:
        print(f'[WARN] Unexpected message count: {len(msgs_db)}')
    c2.close()


async def ws_test(token, conv_id):
    print()
    print('=== Full pipeline test (text -> LLM -> TTS) ===')
    try:
        async with websockets.connect(
            f'{WS_BASE}/ws/chat/{conv_id}?token={token}',
            open_timeout=10
        ) as ws:
            print('[OK] WebSocket connected')

            await ws.send(json.dumps({'type': 'text', 'content': 'Hello, please introduce yourself in one sentence'}))
            print('[OK] Text message sent')

            msgs = []
            llm_chunks = []
            audio_seqs = []

            try:
                while True:
                    raw = await asyncio.wait_for(ws.recv(), timeout=60)
                    m = json.loads(raw)
                    msgs.append(m)
                    t = m.get('type')

                    if t == 'llm_chunk':
                        llm_chunks.append(m.get('text', ''))
                        partial = ''.join(llm_chunks)[-40:]
                        print(f'  llm: ...{partial}', end='\r')
                    elif t == 'audio_chunk':
                        seq = m.get('seq', 0)
                        data_len = len(m.get('data', ''))
                        audio_seqs.append(seq)
                        print(f'  audio_chunk[seq={seq}] base64={data_len}  ')
                    elif t == 'done':
                        print(f'  done msg_id={m.get("message_id")}')
                        break
                    elif t == 'error':
                        print(f'  ERROR: {m.get("message", "")}')
                        break
                    elif t == 'title_updated':
                        print(f'  title_updated: "{m.get("title")}"')

            except asyncio.TimeoutError:
                print('  (timeout after 60s)')

            llm_text = ''.join(llm_chunks)
            types = [m['type'] for m in msgs]
            print()
            print(f'Types: {types}')
            print(f'LLM reply: "{llm_text[:80]}"')
            print(f'Audio chunks: {len(audio_seqs)} (seqs={audio_seqs})')

            print('[OK] LLM streaming output' if llm_chunks else '[FAIL] No LLM output')
            print(f'[OK] TTS audio generated: {len(audio_seqs)} chunks' if audio_seqs else '[FAIL] No TTS audio')
            print('[OK] Pipeline done' if 'done' in types else '[FAIL] No done message')

            if audio_seqs:
                ordered = audio_seqs == sorted(audio_seqs)
                print('[OK] Audio seq order correct' if ordered else f'[FAIL] seq out of order: {audio_seqs}')

    except Exception as e:
        import traceback
        print(f'[FAIL] Exception: {e}')
        traceback.print_exc()


if __name__ == '__main__':
    run()
