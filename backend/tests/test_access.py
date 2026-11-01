from conftest import login


def test_bad_password_is_rejected(client):
    result = client.post("/api/auth/login", json={"username": "student", "password": "wrong"})
    assert result.status_code == 401


def test_login_and_course_membership(client):
    headers = login(client)
    result = client.get("/api/courses", headers=headers)
    assert result.status_code == 200
    assert [c["id"] for c in result.json()] == [1, 2, 3]
    from app.models import Course
    with client.app.state.Session() as db:
        db.add(Course(id=4, title="未加入课程", code="PRIVATE", teacher_id=2))
        db.commit()
    assert client.get("/api/courses/4", headers=headers).status_code == 403


def test_student_cannot_read_teacher_dashboard(client, student):
    assert client.get("/api/courses/1/dashboard", headers=student).status_code == 403


def test_student_cannot_access_admin(client, student):
    assert client.get("/api/admin/users", headers=student).status_code == 403


def test_no_token_cannot_read_courses(client):
    assert client.get("/api/courses").status_code == 401
