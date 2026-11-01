from io import BytesIO
from pptx import Presentation
from conftest import login


def upload(client, headers, content, name="课程.txt"):
    return client.post("/api/courses/1/materials", headers=headers, files={"file": (name, content)})


def ask(client, headers, question, **extra):
    return client.post("/api/courses/1/chat", headers=headers, json={"question": question, **extra})


def test_pptx_citation_tracks_real_slide(client, teacher, student):
    deck = Presentation()
    for text in ["课程介绍", "最左前缀原则：联合索引从最左列开始匹配，跳过最左列可能无法利用该索引。"]:
        slide = deck.slides.add_slide(deck.slide_layouts[1])
        slide.shapes.title.text = text
    buffer = BytesIO()
    deck.save(buffer)
    material = upload(client, teacher, buffer.getvalue(), "测试课件.pptx")
    assert material.status_code == 200, material.text
    response = ask(client, student, "最左前缀原则")
    assert response.status_code == 200, response.text
    citations = response.json()["answer"]["citations"]
    found = [c for c in citations if c["filename"] == "测试课件.pptx"]
    assert found and found[0]["location"] == "第 2 页"
    assert "从最左列" in found[0]["text"]


def test_deleted_material_is_not_retrieved_and_snapshot_survives(client, teacher, student):
    material = upload(client, teacher, "斑马测试知识点：这是唯一的斑马课程资料。".encode()).json()
    result = ask(client, student, "斑马测试知识点").json()
    assert any(c["material_id"] == material["id"] for c in result["answer"]["citations"])
    assert client.delete(f'/api/materials/{material["id"]}', headers=teacher).status_code == 200
    again = ask(client, student, "斑马测试知识点").json()
    assert not again["answer"]["citations"]
    history = client.get(f'/api/conversations/{result["conversation_id"]}', headers=student).json()
    assert any(c["material_id"] == material["id"] for m in history["messages"] for c in m["citations"])


def test_unknown_topic_has_no_fabricated_citations(client, student):
    result = ask(client, student, "如何烘焙提拉米苏蛋糕").json()
    assert result["answer"]["citations"] == []
    assert result["answer"]["grounded"] is False


def test_student_cannot_upload_or_read_other_conversation(client, teacher, student):
    assert upload(client, student, b"data").status_code == 403
    conversation = ask(client, student, "最左前缀原则").json()["conversation_id"]
    other = login(client, "student2")
    assert client.get(f"/api/conversations/{conversation}", headers=other).status_code == 403


def test_empty_and_invalid_documents_are_reported(client, teacher):
    result = upload(client, teacher, b"", "empty.pdf")
    assert result.status_code == 400
    result = upload(client, teacher, b"not a pdf", "broken.pdf")
    assert result.status_code == 200
    assert result.json()["status"] == "failed"
    assert result.json()["error"]
