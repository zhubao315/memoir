"""全局逻辑隔离测试：不同用户拥有独立空间，跨用户访问必须被拒绝。"""

from conftest import register_and_login


def test_users_have_separate_dashboards(client):
    _, ha = register_and_login(client, "iso_a")
    _, hb = register_and_login(client, "iso_b")

    client.post('/api/v1/memories', headers=ha, json={'title': 'A的秘密记忆', 'raw_content': '只在A的空间里'})
    client.post('/api/v1/memories', headers=hb, json={'title': 'B的记忆', 'raw_content': '只在B的空间里'})

    a = client.get('/api/v1/dashboard/summary', headers=ha).json()
    b = client.get('/api/v1/dashboard/summary', headers=hb).json()
    titles_a = [m['title'] for m in a['recent_memories']]
    titles_b = [m['title'] for m in b['recent_memories']]
    assert 'A的秘密记忆' in titles_a and 'B的记忆' not in titles_a
    assert 'B的记忆' in titles_b and 'A的秘密记忆' not in titles_b


def test_rag_only_uses_own_memories(client):
    _, ha = register_and_login(client, "rag_a")
    _, hb = register_and_login(client, "rag_b")

    client.post('/api/v1/memories', headers=ha, json={
        'title': 'A的童年', 'raw_content': 'A小时候住在上海，喜欢外滩。'})
    client.post('/api/v1/memories', headers=hb, json={
        'title': 'B的童年', 'raw_content': 'B小时候住在成都，喜欢宽窄巷子。'})

    ans_a = client.post('/api/v1/ai/ask', headers=ha, json={'question': '我小时候住在哪里？'}).json()
    ans_b = client.post('/api/v1/ai/ask', headers=hb, json={'question': '我小时候住在哪里？'}).json()
    text_a = str(ans_a)
    text_b = str(ans_b)
    assert '上海' in text_a and '成都' not in text_a
    assert '成都' in text_b and '上海' not in text_b


def test_cross_user_media_access_denied(client):
    _, ha = register_and_login(client, "media_a")
    _, hb = register_and_login(client, "media_b")

    created = client.post('/api/v1/memories', headers=ha, json={'title': 'A的记忆', 'raw_content': 'x'})
    mid = created.json()['id']
    # B 不能把媒体挂到 A 的记忆上
    r = client.post('/api/v1/media/upload', headers=hb, files={'file': ('x.png', b'\x89PNG\r\n\x1a\n' + b'0' * 40, 'image/png')}, data={'memory_id': mid})
    assert r.status_code in (400, 403, 404)
