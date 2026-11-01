from app.models import User, Course, Enrollment, Assignment, Material, KnowledgeChunk, Submission


def test_three_students_have_three_complete_courses(client):
    with client.app.state.Session() as db:
        assert [u.name for u in db.query(User).filter_by(role="student").order_by(User.id)] == ["张三", "李四", "王五"]
        assert db.query(User).filter_by(role="teacher").one().name == "T老师"
        assert db.query(Course).count() == 3
        for course in db.query(Course):
            assert db.query(Enrollment).filter_by(course_id=course.id).count() == 3
            assert db.query(Assignment).filter_by(course_id=course.id).count() >= 3
            lecture = db.query(Material).filter_by(course_id=course.id, status="ready").one()
            assert lecture.size > 0
            assert db.query(KnowledgeChunk).filter_by(material_id=lecture.id).count() >= 3
        assert db.query(Submission).count() == 0
    from conftest import login
    for username in ["student", "student2", "student3"]:
        assert [course["id"] for course in client.get("/api/courses", headers=login(client, username)).json()] == [1, 2, 3]


def test_upgrade_is_idempotent_and_archives_removed_accounts(client):
    from app.migration import upgrade_database
    with client.app.state.Session() as db:
        from app.security import hash_password
        db.add(User(id=99,username="student8",name="旧学生",role="student",password_hash=hash_password("old")))
        db.commit()
        upgrade_database(db,client.app.state.settings)
        upgrade_database(db,client.app.state.settings)
        assert db.query(User).filter_by(role="student").count() == 3
        assert db.get(User,99) is None
        assert db.query(Course).count() == 3


def test_python_java_recommendations_and_plan_use_current_course(client, student):
    for cid,title in [(2,"Python"),(3,"Java")]:
        course = client.get(f"/api/courses/{cid}",headers=student).json()
        assert title in course["title"]
        result = client.post(f"/api/courses/{cid}/plans",headers=student,json={})
        assert result.status_code == 200
        assert title in result.json()["title"]
