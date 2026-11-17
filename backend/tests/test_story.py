"""Core product loop: prompt bank -> interview -> story -> versions -> RAG."""

from conftest import register_and_login


def test_prompt_bank_seeded(client):
    _, h = register_and_login(client, "promptuser")
    prompts = client.get("/api/v1/story/prompts?limit=300", headers=h).json()
    assert len(prompts) >= 200
    cats = client.get("/api/v1/story/prompts/categories", headers=h).json()
    assert len(cats) == 20


def test_interview_and_story_versions(client):
    _, h = register_and_login(client, "storyuser")

    # Create a memory as source material.
    m = client.post(
        "/api/v1/memories",
        headers=h,
        json={"title": "什刹海", "raw_content": "小时候我经常跟父亲去北京什刹海，那段时间很快乐。父亲喜欢划船。"},
    )
    memory_id = m.json()["id"]

    # Generate a first-person story from the memory.
    gen = client.post(
        "/api/v1/story/stories/generate",
        headers=h,
        json={"mode": "first_person", "source_memory_id": memory_id},
    )
    assert gen.status_code == 201, gen.text
    story = gen.json()
    sid = story["id"]

    versions = client.get(f"/api/v1/story/stories/{sid}/versions", headers=h).json()
    assert len(versions) == 1 and versions[0]["is_ai"] is True
    assert versions[0]["provider"] == "mock"  # honest: no fake real provider

    # Human edit creates a NEW version; original AI draft remains.
    edit = client.post(
        f"/api/v1/story/stories/{sid}/versions",
        headers=h,
        json={"content": "我小时候常和父亲去什刹海。", "note": "人工润色"},
    )
    assert edit.status_code == 201
    versions = client.get(f"/api/v1/story/stories/{sid}/versions", headers=h).json()
    assert len(versions) == 2 and any(v["is_ai"] is False for v in versions)

    # Restore keeps all versions.
    restore = client.post(f"/api/v1/story/stories/{sid}/versions/{versions[0]['id']}/restore", headers=h)
    assert restore.status_code == 200
    assert len(client.get(f"/api/v1/story/stories/{sid}/versions", headers=h).json()) == 2

    # RAG asks over user-scoped embeddings and returns citations.
    ask = client.post("/api/v1/ai/ask", headers=h, json={"question": "我小时候住在哪里？"})
    assert ask.status_code == 200
    assert "answer" in ask.json() and "citations" in ask.json()


def test_interview_dynamic_followup(client):
    _, h = register_and_login(client, "interviewuser")
    created = client.post("/api/v1/story/interviews", headers=h, json={"topic": "childhood"})
    assert created.status_code == 201
    iid = created.json()["id"]
    msgs = client.get(f"/api/v1/story/interviews/{iid}/messages", headers=h).json()
    assert len(msgs) == 1 and msgs[0]["role"] == "interviewer"

    answered = client.post(
        f"/api/v1/story/interviews/{iid}/answer",
        headers=h,
        json={"content": "小时候我经常跟父亲去北京什刹海，很快乐。"},
    )
    assert answered.status_code == 200
    msgs = answered.json()
    assert any(m["role"] == "interviewer" for m in msgs)  # dynamic follow-up asked

    finished = client.post(
        f"/api/v1/story/interviews/{iid}/answer",
        headers=h,
        json={"content": "没有什么啦，就这些。", "finish": True},
    )
    assert finished.status_code == 200
