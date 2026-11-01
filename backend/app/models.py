from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Boolean, UniqueConstraint
from .db import Base


def now():
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo("Asia/Shanghai")).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    name = Column(String(80), nullable=False)
    role = Column(String(20), nullable=False)


class Course(Base):
    __tablename__ = "courses"
    id = Column(Integer, primary_key=True)
    title = Column(String(100), nullable=False)
    code = Column(String(30), nullable=False)
    subtitle = Column(String(200), default="")
    class_name = Column(String(100), default="高级软件产品管理1班")
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    description = Column(Text, default="")


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (UniqueConstraint("course_id", "user_id"),)
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)


class Material(Base):
    __tablename__ = "materials"
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    filename = Column(String(256), nullable=False)
    stored_name = Column(String(100), nullable=False)
    status = Column(String(20), default="pending")
    error = Column(Text, default="")
    pages = Column(Integer, default=0)
    size = Column(Integer, default=0)
    is_seed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=now)


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False)
    text = Column(Text, nullable=False)
    location = Column(String(100), nullable=False)
    position = Column(Integer, default=0)


class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=now)


class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    citations = Column(JSON, default=list)
    grounded = Column(Boolean, default=False)
    mode = Column(String(30), default="demo")
    hint_level = Column(Integer, default=1)
    created_at = Column(DateTime, default=now)


class Assignment(Base):
    __tablename__ = "assignments"
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    title = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    topic = Column(String(100), default="SQL 综合")
    rubric = Column(JSON, default=list)
    max_score = Column(Integer, default=100)
    status = Column(String(20), default="draft")
    deadline = Column(DateTime, nullable=True)
    starter_code = Column(Text, default="SELECT * FROM students;")
    grading_rule = Column(String(40), default="manual")
    created_at = Column(DateTime, default=now)


class Submission(Base):
    __tablename__ = "submissions"
    __table_args__ = (UniqueConstraint("student_id", "assignment_id", "request_id"),)
    id = Column(Integer, primary_key=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    request_id = Column(String(100), nullable=False)
    code = Column(Text, nullable=False)
    status = Column(String(30), default="pending")
    error = Column(Text, default="")
    grade = Column(JSON, nullable=True)
    review_history = Column(JSON, default=list)
    attempts = Column(Integer, default=0)
    is_seed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=now)


class Mistake(Base):
    __tablename__ = "mistakes"
    id = Column(Integer, primary_key=True)
    submission_id = Column(Integer, ForeignKey("submissions.id"), unique=True, nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    topic = Column(String(100), nullable=False)
    detail = Column(Text, nullable=False)
    status = Column(String(20), default="pending")
    created_at = Column(DateTime, default=now)


class StudyPlan(Base):
    __tablename__ = "study_plans"
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(100), nullable=False)
    basis = Column(Text, default="")
    created_at = Column(DateTime, default=now)


class PlanItem(Base):
    __tablename__ = "plan_items"
    id = Column(Integer, primary_key=True)
    plan_id = Column(Integer, ForeignKey("study_plans.id"), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, default="")
    duration = Column(Integer, default=20)
    done = Column(Boolean, default=False)


class AgentConfig(Base):
    __tablename__ = "agent_configs"
    course_id = Column(Integer, ForeignKey("courses.id"), primary_key=True)
    persona = Column(String(200), default="耐心、严谨的数据库课程助教")
    prompt = Column(Text, default="依据课程资料回答。先引导学生思考，再给出提示；不捏造引用。")
    hint_first = Column(Boolean, default=True)
    max_hint_level = Column(Integer, default=3)


class LearningEvent(Base):
    __tablename__ = "learning_events"
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    kind = Column(String(40), nullable=False)
    text = Column(String(250), nullable=False)
    is_seed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=now)


class PracticeSession(Base):
    __tablename__ = "practice_sessions"
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    mode = Column(String(20), nullable=False)
    count = Column(Integer, default=3, nullable=False)
    status = Column(String(30), default="pending", nullable=False)
    error = Column(Text, default="")
    questions = Column(JSON, default=list)
    answers = Column(JSON, default=list)
    feedback = Column(JSON, nullable=True)
    request_id = Column(String(100), nullable=True)
    ai_mode = Column(String(30), default="demo")
    attempts = Column(Integer, default=0)
    created_at = Column(DateTime, default=now)


class Report(Base):
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    scope = Column(String(20), default="personal", nullable=False)
    status = Column(String(30), default="pending", nullable=False)
    error = Column(Text, default="")
    title = Column(String(200), default="")
    content = Column(Text, default="")
    statistics = Column(JSON, default=dict)
    storage_key = Column(String(256), default="")
    ai_mode = Column(String(30), default="demo")
    attempts = Column(Integer, default=0)
    created_at = Column(DateTime, default=now)


class Execution(Base):
    __tablename__ = "executions"
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    language = Column(String(20), nullable=False)
    code = Column(Text, nullable=False)
    stdin = Column(Text, default="")
    status = Column(String(30), default="pending", nullable=False)
    error = Column(Text, default="")
    token = Column(String(100), default="")
    result = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=now)
