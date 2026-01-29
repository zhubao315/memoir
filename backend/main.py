"""
数字人生回忆录 - 后端API (FastAPI)
MVP版本 - 使用SQLite作为临时数据库
"""

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, DateTime, JSON, ForeignKey, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.sql import func
from datetime import datetime, timedelta
from typing import List, Optional
from pydantic import BaseModel
from jose import JWTError, jwt
import bcrypt
import os
import json
import uuid
from pathlib import Path

# ==================== 配置 ====================
SECRET_KEY = "memoir-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7天

# 数据库配置
SQLALCHEMY_DATABASE_URL = "sqlite:///./memoir.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

security = HTTPBearer()

# 文件上传目录
UPLOAD_DIR = Path("/fs/memoir/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ==================== 数据模型 ====================
class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    entries = relationship("Entry", back_populates="user", cascade="all, delete-orphan")
    tags = relationship("Tag", back_populates="user", cascade="all, delete-orphan")

class Entry(Base):
    __tablename__ = "entries"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"))
    title = Column(String, nullable=False)
    content = Column(Text)
    entry_date = Column(String, nullable=False)  # YYYY-MM-DD
    entry_type = Column(String, default="memory")  # memory, milestone, daily, travel
    mood = Column(String, default="neutral")  # happy, sad, excited, calm, angry, neutral
    location = Column(JSON, default=dict)  # {"lat": 39.9, "lng": 116.4, "name": "Beijing"}
    tags = Column(JSON, default=list)  # ["tag1", "tag2"]
    is_public = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="entries")
    media = relationship("Media", back_populates="entry", cascade="all, delete-orphan")

class Media(Base):
    __tablename__ = "media"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    entry_id = Column(String, ForeignKey("entries.id"))
    user_id = Column(String, ForeignKey("users.id"))
    filename = Column(String, nullable=False)
    file_type = Column(String, default="photo")  # photo, video, audio
    file_path = Column(String, nullable=False)
    file_size = Column(Integer)
    mime_type = Column(String)
    caption = Column(Text)
    taken_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now())

    entry = relationship("Entry", back_populates="media")

class Tag(Base):
    __tablename__ = "tags"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"))
    name = Column(String, nullable=False)
    color = Column(String, default="#6366f1")
    icon = Column(String)
    created_at = Column(DateTime, default=func.now())

    user = relationship("User", back_populates="tags")

# 创建表
Base.metadata.create_all(bind=engine)

# ==================== Pydantic模型 ====================
class UserCreate(BaseModel):
    username: str
    email: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    created_at: datetime

    class Config:
        from_attributes = True

class EntryCreate(BaseModel):
    title: str
    content: Optional[str] = None
    entry_date: str
    entry_type: Optional[str] = "memory"
    mood: Optional[str] = "neutral"
    location: Optional[dict] = None
    tags: Optional[List[str]] = None
    is_public: Optional[bool] = False

class EntryUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    entry_date: Optional[str] = None
    entry_type: Optional[str] = None
    mood: Optional[str] = None
    location: Optional[dict] = None
    tags: Optional[List[str]] = None
    is_public: Optional[bool] = None

class EntryResponse(BaseModel):
    id: str
    user_id: str
    title: str
    content: Optional[str]
    entry_date: str
    entry_type: str
    mood: str
    location: Optional[dict]
    tags: List[str]
    is_public: bool
    created_at: datetime
    updated_at: datetime
    media_count: int = 0

    class Config:
        from_attributes = True

class MediaResponse(BaseModel):
    id: str
    filename: str
    file_type: str
    caption: Optional[str]
    taken_at: Optional[datetime]

    class Config:
        from_attributes = True

class TagCreate(BaseModel):
    name: str
    color: Optional[str] = "#6366f1"
    icon: Optional[str] = None

class TagResponse(BaseModel):
    id: str
    name: str
    color: str
    icon: Optional[str]

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

# ==================== 工具函数 ====================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except:
        return False

def get_password_hash(password: str) -> str:
    """使用bcrypt生成密码哈希"""
    # bcrypt限制密码长度为72字节
    if len(password.encode('utf-8')) > 72:
        password = password[:72].encode('utf-8').decode('utf-8', 'ignore')

    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: SessionLocal = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user

# ==================== FastAPI应用 ====================
app = FastAPI(title="数字人生回忆录", version="0.1.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== 认证路由 ====================
@app.post("/api/auth/register", response_model=UserResponse)
def register(user: UserCreate, db: SessionLocal = Depends(get_db)):
    # 检查用户名或邮箱是否已存在
    if db.query(User).filter(User.username == user.username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(status_code=400, detail="邮箱已存在")

    # 创建用户
    hashed_password = get_password_hash(user.password)
    db_user = User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.post("/api/auth/login", response_model=Token)
def login(user: UserLogin, db: SessionLocal = Depends(get_db)):
    db_user = db.query(User).filter(User.username == user.username).first()
    if not db_user or not verify_password(user.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    access_token_expires = timedelta(days=7)
    access_token = create_access_token(
        data={"sub": db_user.username}, expires_delta=access_token_expires
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": db_user
    }

@app.get("/api/auth/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_user)):
    return current_user

# ==================== 记忆条目路由 ====================
@app.get("/api/entries", response_model=List[EntryResponse])
def get_entries(
    skip: int = 0,
    limit: int = 50,
    entry_type: Optional[str] = None,
    mood: Optional[str] = None,
    tag: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: SessionLocal = Depends(get_db)
):
    query = db.query(Entry).filter(Entry.user_id == current_user.id)

    if entry_type:
        query = query.filter(Entry.entry_type == entry_type)
    if mood:
        query = query.filter(Entry.mood == mood)
    if tag:
        query = query.filter(Entry.tags.contains(tag))

    entries = query.order_by(Entry.entry_date.desc()).offset(skip).limit(limit).all()

    # 添加media_count
    for entry in entries:
        entry.media_count = db.query(Media).filter(Media.entry_id == entry.id).count()

    return entries

@app.get("/api/entries/{entry_id}", response_model=EntryResponse)
def get_entry(entry_id: str, current_user: User = Depends(get_current_user), db: SessionLocal = Depends(get_db)):
    entry = db.query(Entry).filter(Entry.id == entry_id, Entry.user_id == current_user.id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="记忆条目不存在")

    entry.media_count = db.query(Media).filter(Media.entry_id == entry.id).count()
    return entry

@app.post("/api/entries", response_model=EntryResponse)
def create_entry(entry: EntryCreate, current_user: User = Depends(get_current_user), db: SessionLocal = Depends(get_db)):
    db_entry = Entry(
        user_id=current_user.id,
        title=entry.title,
        content=entry.content,
        entry_date=entry.entry_date,
        entry_type=entry.entry_type,
        mood=entry.mood,
        location=entry.location or {},
        tags=entry.tags or [],
        is_public=entry.is_public
    )
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    return db_entry

@app.put("/api/entries/{entry_id}", response_model=EntryResponse)
def update_entry(entry_id: str, entry: EntryUpdate, current_user: User = Depends(get_current_user), db: SessionLocal = Depends(get_db)):
    db_entry = db.query(Entry).filter(Entry.id == entry_id, Entry.user_id == current_user.id).first()
    if not db_entry:
        raise HTTPException(status_code=404, detail="记忆条目不存在")

    if entry.title is not None:
        db_entry.title = entry.title
    if entry.content is not None:
        db_entry.content = entry.content
    if entry.entry_date is not None:
        db_entry.entry_date = entry.entry_date
    if entry.entry_type is not None:
        db_entry.entry_type = entry.entry_type
    if entry.mood is not None:
        db_entry.mood = entry.mood
    if entry.location is not None:
        db_entry.location = entry.location
    if entry.tags is not None:
        db_entry.tags = entry.tags
    if entry.is_public is not None:
        db_entry.is_public = entry.is_public

    db.commit()
    db.refresh(db_entry)
    return db_entry

@app.delete("/api/entries/{entry_id}")
def delete_entry(entry_id: str, current_user: User = Depends(get_current_user), db: SessionLocal = Depends(get_db)):
    db_entry = db.query(Entry).filter(Entry.id == entry_id, Entry.user_id == current_user.id).first()
    if not db_entry:
        raise HTTPException(status_code=404, detail="记忆条目不存在")

    # 删除关联的媒体文件
    media_files = db.query(Media).filter(Media.entry_id == entry_id).all()
    for media in media_files:
        try:
            file_path = UPLOAD_DIR / media.file_path
            if file_path.exists():
                file_path.unlink()
        except:
            pass

    db.delete(db_entry)
    db.commit()
    return {"message": "删除成功"}

# ==================== 媒体文件路由 ====================
@app.post("/api/entries/{entry_id}/media", response_model=MediaResponse)
async def upload_media(
    entry_id: str,
    file: UploadFile = File(...),
    caption: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: SessionLocal = Depends(get_db)
):
    # 验证条目存在
    entry = db.query(Entry).filter(Entry.id == entry_id, Entry.user_id == current_user.id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="记忆条目不存在")

    # 保存文件
    file_ext = Path(file.filename).suffix.lower()
    file_type = "photo"
    if file_ext in [".mp4", ".avi", ".mov", ".mkv"]:
        file_type = "video"
    elif file_ext in [".mp3", ".wav", ".m4a", ".ogg"]:
        file_type = "audio"

    # 生成唯一文件名
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = f"{current_user.id}/{entry_id}/{unique_filename}"
    full_path = UPLOAD_DIR / file_path
    full_path.parent.mkdir(parents=True, exist_ok=True)

    # 保存文件
    with open(full_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)

    # 创建媒体记录
    db_media = Media(
        entry_id=entry_id,
        user_id=current_user.id,
        filename=file.filename,
        file_type=file_type,
        file_path=file_path,
        file_size=len(content),
        mime_type=file.content_type,
        caption=caption
    )
    db.add(db_media)
    db.commit()
    db.refresh(db_media)

    return db_media

@app.get("/api/entries/{entry_id}/media", response_model=List[MediaResponse])
def get_media(entry_id: str, current_user: User = Depends(get_current_user), db: SessionLocal = Depends(get_db)):
    entry = db.query(Entry).filter(Entry.id == entry_id, Entry.user_id == current_user.id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="记忆条目不存在")

    media = db.query(Media).filter(Media.entry_id == entry_id).all()
    return media

@app.delete("/api/media/{media_id}")
def delete_media(media_id: str, current_user: User = Depends(get_current_user), db: SessionLocal = Depends(get_db)):
    media = db.query(Media).filter(Media.id == media_id, Media.user_id == current_user.id).first()
    if not media:
        raise HTTPException(status_code=404, detail="媒体文件不存在")

    # 删除物理文件
    try:
        file_path = UPLOAD_DIR / media.file_path
        if file_path.exists():
            file_path.unlink()
    except:
        pass

    db.delete(media)
    db.commit()
    return {"message": "删除成功"}

# ==================== 标签路由 ====================
@app.get("/api/tags", response_model=List[TagResponse])
def get_tags(current_user: User = Depends(get_current_user), db: SessionLocal = Depends(get_db)):
    tags = db.query(Tag).filter(Tag.user_id == current_user.id).all()
    return tags

@app.post("/api/tags", response_model=TagResponse)
def create_tag(tag: TagCreate, current_user: User = Depends(get_current_user), db: SessionLocal = Depends(get_db)):
    # 检查标签是否已存在
    existing_tag = db.query(Tag).filter(Tag.user_id == current_user.id, Tag.name == tag.name).first()
    if existing_tag:
        raise HTTPException(status_code=400, detail="标签已存在")

    db_tag = Tag(
        user_id=current_user.id,
        name=tag.name,
        color=tag.color,
        icon=tag.icon
    )
    db.add(db_tag)
    db.commit()
    db.refresh(db_tag)
    return db_tag

@app.delete("/api/tags/{tag_id}")
def delete_tag(tag_id: str, current_user: User = Depends(get_current_user), db: SessionLocal = Depends(get_db)):
    tag = db.query(Tag).filter(Tag.id == tag_id, Tag.user_id == current_user.id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="标签不存在")

    # 从所有条目中移除该标签
    entries = db.query(Entry).filter(Entry.user_id == current_user.id).all()
    for entry in entries:
        if tag.name in entry.tags:
            entry.tags.remove(tag.name)

    db.delete(tag)
    db.commit()
    return {"message": "删除成功"}

# ==================== 统计信息 ====================
@app.get("/api/stats")
def get_stats(current_user: User = Depends(get_current_user), db: SessionLocal = Depends(get_db)):
    total_entries = db.query(Entry).filter(Entry.user_id == current_user.id).count()
    total_media = db.query(Media).filter(Media.user_id == current_user.id).count()
    total_tags = db.query(Tag).filter(Tag.user_id == current_user.id).count()

    # 按类型统计
    entry_types = db.query(Entry.entry_type, func.count(Entry.id)).filter(
        Entry.user_id == current_user.id
    ).group_by(Entry.entry_type).all()

    # 按情绪统计
    moods = db.query(Entry.mood, func.count(Entry.id)).filter(
        Entry.user_id == current_user.id
    ).group_by(Entry.mood).all()

    # 最近7天的条目
    recent_entries = db.query(Entry).filter(
        Entry.user_id == current_user.id,
        Entry.created_at >= datetime.utcnow() - timedelta(days=7)
    ).count()

    return {
        "total_entries": total_entries,
        "total_media": total_media,
        "total_tags": total_tags,
        "entry_types": {row[0]: row[1] for row in entry_types},
        "moods": {row[0]: row[1] for row in moods},
        "recent_entries": recent_entries
    }

# ==================== 根路由 ====================
@app.get("/")
def root():
    return {
        "message": "数字人生回忆录 API",
        "version": "0.1.0",
        "docs": "/docs",
        "status": "running"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
