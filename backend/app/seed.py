from datetime import timedelta
from pptx import Presentation
from .models import User, Course, Enrollment, AgentConfig, Assignment, Material, KnowledgeChunk, now
from .security import hash_password
from .services.course_content import COURSES, RUBRIC

ROSTER = [(1, 'student', '张三', 'student'), (2, 'teacher', 'T老师', 'teacher'),
          (3, 'admin', '管理员', 'admin'), (4, 'student2', '李四', 'student'), (5, 'student3', '王五', 'student')]
LESSONS = COURSES[1]['lessons']


def ensure_course_content(db, settings, teacher_id):
    """Fill absent content without rewriting teacher work or historical assignments."""
    added = dict.fromkeys(['courses', 'enrollments', 'agent_configs', 'assignments', 'materials', 'knowledge_chunks'], 0)
    for cid, content in COURSES.items():
        if db.get(Course, cid) is None:
            db.add(Course(id=cid, teacher_id=teacher_id, **{k: content[k] for k in ('title', 'code', 'subtitle', 'description')}))
            db.flush()
            added['courses'] += 1
        if db.get(AgentConfig, cid) is None:
            db.add(AgentConfig(course_id=cid, persona=f"耐心、严谨的{content['title']}助教"))
            added['agent_configs'] += 1
        for user in db.query(User).filter_by(role='student'):
            if not db.query(Enrollment).filter_by(course_id=cid, user_id=user.id).first():
                db.add(Enrollment(course_id=cid, user_id=user.id))
                added['enrollments'] += 1
        for title, topic, description, rule, code in content['assignments']:
            if db.query(Assignment).filter_by(course_id=cid, title=title).first():
                continue
            db.add(Assignment(course_id=cid, title=title, topic=topic, description=description, grading_rule=rule,
                              starter_code=code, rubric=RUBRIC, status='published', deadline=now() + timedelta(days=14)))
            added['assignments'] += 1
        stored = f'course_{cid}_lecture_v1.pptx'
        if not db.query(Material).filter_by(course_id=cid, stored_name=stored).first():
            path = settings.uploads / stored
            deck = Presentation()
            for title, text in content['lessons']:
                slide = deck.slides.add_slide(deck.slide_layouts[1])
                slide.shapes.title.text = title
                slide.placeholders[1].text = text
            deck.save(str(path))
            material = Material(course_id=cid, filename=f"{content['title']}_课程讲义.pptx", stored_name=stored,
                                status='ready', pages=len(content['lessons']), size=path.stat().st_size, is_seed=True)
            db.add(material)
            db.flush()
            added['materials'] += 1
            for index, (title, text) in enumerate(content['lessons']):
                db.add(KnowledgeChunk(course_id=cid, material_id=material.id, text=f'{title}\n{text}', location=f'第 {index+1} 页', position=index))
                added['knowledge_chunks'] += 1
    db.flush()
    return added


def seed_database(db, settings):
    """Initialize empty installations. Existing installations require app.migration."""
    if db.query(User).first():
        return
    hashed = hash_password('Demo12345!')
    for uid, username, name, role in ROSTER:
        db.add(User(id=uid, username=username, name=name, role=role, password_hash=hashed))
    db.flush()
    ensure_course_content(db, settings, teacher_id=2)
    db.commit()
