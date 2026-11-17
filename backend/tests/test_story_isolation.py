"""Story Studio 资源级隔离（IDOR）回归测试。

场景：用户 A 创建记忆 / 访谈 / 录音 / 逐字稿 / 故事；用户 B 尝试用 A 的资源 id
直接读取、生成故事、编辑逐字稿、恢复版本等，必须全部被拒绝（404），
且不泄漏任何内容。"""

from conftest import register_and_login


def _me(client, headers):
    return client.get('/api/v1/auth/me', headers=headers).json()


def _make_memory(client, headers, raw):
    r = client.post('/api/v1/memories', headers=headers, json={'title': '私有记忆', 'raw_content': raw})
    assert r.status_code in (200, 201), r.text
    return r.json()['id']


def _make_recording_with_transcript(client, headers, content: str):
    """直接入库一段属于当前用户的录音 + 逐字稿，跳过异步 ASR。"""
    from app.db.session import SessionLocal
    from app.models.media import MediaAsset, Recording, Transcript
    from app.models.story import Interview

    me = _me(client, headers)
    db = SessionLocal()
    try:
        asset = MediaAsset(
            user_id=me['id'],
            storage_key=f"test/{me['id']}/a.webm",
            media_type='audio',
            mime_type='audio/webm',
            original_filename='a.webm',
        )
        db.add(asset)
        db.flush()
        rec = Recording(
            user_id=me['id'],
            media_asset_id=asset.id,
            status='transcribed',
            mime_type='audio/webm',
        )
        db.add(rec)
        db.flush()
        tr = Transcript(recording_id=rec.id, user_id=me['id'], content=content, engine='mock')
        db.add(tr)
        # 另建一段属于该用户的访谈，便于访谈隔离测试。
        interview = Interview(user_id=me['id'], topic='childhood', title='我的访谈', status='completed')
        db.add(interview)
        db.flush()
        return rec.id, tr.id, interview.id
    finally:
        db.commit()
        db.close()


def test_source_text_generation_rejects_foreign_memory(client):
    """核心 IDOR：用他人 memory_id 生成故事必须 404，而非读取其内容。"""
    _, ha = register_and_login(client, 'idor_alice')
    _, hb = register_and_login(client, 'idor_bob')
    alice_memory = _make_memory(client, ha, '爱丽丝的私密童年往事，只有她自己能读到。')

    r = client.post(
        '/api/v1/story/stories/generate',
        headers=hb,
        json={'mode': 'first_person', 'source_memory_id': alice_memory},
    )
    assert r.status_code == 404, r.text
    assert '内容' not in r.text  # 不泄漏原始内容


def test_source_text_generation_rejects_foreign_recording(client):
    _, ha = register_and_login(client, 'idor_rec_alice')
    _, hb = register_and_login(client, 'idor_rec_bob')
    rid, _, _ = _make_recording_with_transcript(client, ha, '爱丽丝的口述录音内容。')

    r = client.post(
        '/api/v1/story/stories/generate',
        headers=hb,
        json={'mode': 'first_person', 'source_recording_id': rid},
    )
    assert r.status_code == 404, r.text


def test_source_text_generation_rejects_foreign_interview(client):
    _, ha = register_and_login(client, 'idor_int_alice')
    _, hb = register_and_login(client, 'idor_int_bob')
    _, _, iid = _make_recording_with_transcript(client, ha, 'unused')

    r = client.post(
        '/api/v1/story/stories/generate',
        headers=hb,
        json={'mode': 'first_person', 'source_interview_id': iid},
    )
    assert r.status_code == 404, r.text


def test_recording_and_transcript_cross_user_denied(client):
    _, ha = register_and_login(client, 'idor_media_alice')
    _, hb = register_and_login(client, 'idor_media_bob')
    rid, tid, _ = _make_recording_with_transcript(client, ha, '爱丽丝的逐字稿原文。')

    # 读取录音详情 / 修正逐字稿均须 404。
    assert client.get(f'/api/v1/story/recordings/{rid}', headers=hb).status_code == 404
    assert client.put(
        f'/api/v1/story/transcripts/{tid}', headers=hb, json={'content': '篡改'}
    ).status_code == 404

    # 所有者自己可以读取；返回真实 ASR 引擎名与播放地址字段。
    own = client.get(f'/api/v1/story/recordings/{rid}', headers=ha)
    assert own.status_code == 200, own.text
    body = own.json()
    assert body['transcripts'][0]['content'] == '爱丽丝的逐字稿原文。'
    assert body['transcripts'][0]['engine'] == 'mock'
    assert 'play_url' in body

    # 所有者修正逐字稿：原始转写保留，新增一条 corrected 记录。
    corr = client.put(
        f'/api/v1/story/transcripts/{tid}', headers=ha, json={'content': '修正后的逐字稿'}
    )
    assert corr.status_code == 200, corr.text
    detail = client.get(f'/api/v1/story/recordings/{rid}', headers=ha).json()
    assert any(t['content'] == '修正后的逐字稿' and t['is_corrected'] for t in detail['transcripts'])
    assert any(t['content'] == '爱丽丝的逐字稿原文。' for t in detail['transcripts'])


def test_interview_cross_user_denied(client):
    _, ha = register_and_login(client, 'idor_iv_alice')
    _, hb = register_and_login(client, 'idor_iv_bob')
    created = client.post('/api/v1/story/interviews', headers=ha, json={'topic': 'childhood'})
    assert created.status_code == 201, created.text
    iid = created.json()['id']

    # 列表、详情、消息、回答、暂停全部拒绝。
    assert all(i['id'] != iid for i in client.get('/api/v1/story/interviews', headers=hb).json())
    assert client.get(f'/api/v1/story/interviews/{iid}', headers=hb).status_code == 404
    assert client.get(f'/api/v1/story/interviews/{iid}/messages', headers=hb).status_code == 404
    assert client.post(
        f'/api/v1/story/interviews/{iid}/answer', headers=hb, json={'content': '入侵回答'}
    ).status_code == 404
    assert client.post(f'/api/v1/story/interviews/{iid}/pause', headers=hb).status_code == 404

    # 所有者消息未被污染。
    msgs = client.get(f'/api/v1/story/interviews/{iid}/messages', headers=ha).json()
    assert all('入侵回答' not in m['content'] for m in msgs)


def test_answer_cross_user_recording_rejected(client):
    """访谈回答中挂载他人 recording_id 必须 404。"""
    _, ha = register_and_login(client, 'idor_ans_alice')
    _, hb = register_and_login(client, 'idor_ans_bob')
    rid, _, _ = _make_recording_with_transcript(client, ha, '爱丽丝的录音')
    created = client.post('/api/v1/story/interviews', headers=hb, json={'topic': 'childhood'})
    iid = created.json()['id']

    r = client.post(
        f'/api/v1/story/interviews/{iid}/answer',
        headers=hb,
        json={'content': '我的回答', 'recording_id': rid},
    )
    assert r.status_code == 404, r.text


def test_create_recording_cross_user_asset_and_interview_rejected(client):
    """创建录音时引用他人媒体资产 / 访谈必须 404。"""
    _, ha = register_and_login(client, 'idor_cr_alice')
    _, hb = register_and_login(client, 'idor_cr_bob')
    rid, _, iid = _make_recording_with_transcript(client, ha, 'unused')

    # 借用爱丽丝的访谈 id（合法资产情况下仍须拒绝）。
    from app.db.session import SessionLocal
    from app.models.media import MediaAsset

    db = SessionLocal()
    try:
        me = _me(client, hb)
        asset = MediaAsset(
            user_id=me['id'],
            storage_key=f"test/{me['id']}/b.webm",
            media_type='audio',
            mime_type='audio/webm',
            original_filename='b.webm',
        )
        db.add(asset)
        db.commit()
        asset_id = asset.id
    finally:
        db.close()

    r = client.post(
        '/api/v1/story/recordings',
        headers=hb,
        json={'media_asset_id': asset_id, 'interview_id': iid},
    )
    assert r.status_code == 404, r.text

    # 借用他人的媒体资产 id 同样拒绝。
    r2 = client.post(
        '/api/v1/story/recordings',
        headers=hb,
        json={'media_asset_id': rid},  # rid 不是资产 id，但预期都不应成功
    )
    assert r2.status_code in (400, 404)


def test_story_versions_cross_user_denied(client):
    """故事的版本列表、编辑、恢复、当前版本、重生成均须归属校验。"""
    _, ha = register_and_login(client, 'idor_story_alice')
    _, hb = register_and_login(client, 'idor_story_bob')
    am = _make_memory(client, ha, '爱丽丝的故事素材。')
    gen = client.post(
        '/api/v1/story/stories/generate',
        headers=ha,
        json={'mode': 'first_person', 'source_memory_id': am},
    )
    assert gen.status_code == 201, gen.text
    sid = gen.json()['id']
    versions = client.get(f'/api/v1/story/stories/{sid}/versions', headers=ha).json()
    vid = versions[0]['id']

    paths = [
        ('get', f'/api/v1/story/stories/{sid}', None),
        ('get', f'/api/v1/story/stories/{sid}/versions', None),
        ('get', f'/api/v1/story/stories/{sid}/current', None),
        ('post', f'/api/v1/story/stories/{sid}/versions', {'content': '篡改', 'note': 'x'}),
        ('post', f'/api/v1/story/stories/{sid}/versions/{vid}/restore', None),
        ('post', f'/api/v1/story/stories/{sid}/regenerate', {'mode': 'literary'}),
        ('put', f'/api/v1/story/stories/{sid}/visibility', {'visibility': 'public'}),
        ('delete', f'/api/v1/story/stories/{sid}', None),
    ]
    for method, url, body in paths:
        if method == 'get':
            r = client.get(url, headers=hb)
        elif method == 'post':
            r = client.post(url, headers=hb, json=body)
        elif method == 'put':
            r = client.put(url, headers=hb, json=body)
        else:
            r = client.delete(url, headers=hb)
        assert r.status_code == 404, f'{method} {url} -> {r.status_code}: {r.text}'

    # 故事列表不含爱丽丝的故事。
    assert all(s['id'] != sid for s in client.get('/api/v1/story/stories', headers=hb).json())
