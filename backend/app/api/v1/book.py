"""Legacy Book: builder, chapters, exports (PDF/Markdown/JSON) & QR codes."""

from __future__ import annotations

import json
import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user, get_db
from app.core.security import utcnow
from app.models.publishing import Book, BookChapter, BookExportJob, BookQRCode
from app.models.story import Story, StoryVersion

router = APIRouter(prefix="/book", tags=["legacy-book"])


class BookIn(BaseModel):
    title: str
    subtitle: str | None = None
    author: str | None = None
    template: str = "classic"
    family_id: str | None = None


class ChapterIn(BaseModel):
    title: str
    intro: str | None = None
    content: str | None = None
    story_ids: list[str] | None = None
    media_ids: list[str] | None = None
    order_index: int = 0


@router.post("", status_code=201)
def create_book(payload: BookIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    book = Book(
        user_id=user.id, family_id=payload.family_id, title=payload.title,
        subtitle=payload.subtitle, author=payload.author, template=payload.template,
    )
    db.add(book)
    db.commit()
    db.refresh(book)
    return book


@router.get("")
def list_books(user=Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Book).filter(Book.user_id == user.id, Book.deleted_at.is_(None)).all()


@router.get("/{book_id}")
def get_book(book_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    book = db.query(Book).filter(Book.id == book_id, Book.user_id == user.id).first()
    if not book:
        raise HTTPException(status_code=404, detail="回忆录不存在")
    chapters = db.query(BookChapter).filter(BookChapter.book_id == book_id).order_by(BookChapter.order_index).all()
    return {"book": book, "chapters": chapters}


@router.post("/{book_id}/chapters", status_code=201)
def add_chapter(book_id: str, payload: ChapterIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    book = db.query(Book).filter(Book.id == book_id, Book.user_id == user.id).first()
    if not book:
        raise HTTPException(status_code=404, detail="回忆录不存在")
    ch = BookChapter(book_id=book_id, **payload.model_dump())
    db.add(ch)
    db.commit()
    db.refresh(ch)
    return ch


@router.put("/chapters/{chapter_id}")
def update_chapter(chapter_id: str, payload: ChapterIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    ch = db.query(BookChapter).filter(BookChapter.id == chapter_id).first()
    if not ch:
        raise HTTPException(status_code=404, detail="章节不存在")
    book = db.query(Book).filter(Book.id == ch.book_id, Book.user_id == user.id).first()
    if not book:
        raise HTTPException(status_code=403, detail="无权修改")
    for k, v in payload.model_dump().items():
        setattr(ch, k, v)
    db.commit()
    return ch


@router.delete("/chapters/{chapter_id}")
def delete_chapter(chapter_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    ch = db.query(BookChapter).filter(BookChapter.id == chapter_id).first()
    if not ch:
        raise HTTPException(status_code=404, detail="章节不存在")
    book = db.query(Book).filter(Book.id == ch.book_id, Book.user_id == user.id).first()
    if not book:
        raise HTTPException(status_code=403, detail="无权删除")
    db.delete(ch)
    db.commit()
    return {"message": "章节已删除"}


def _render_markdown(db: Session, book: Book) -> str:
    lines = [f"# {book.title}", "", book.subtitle or "", f"作者：{book.author or ''}", ""]
    for ch in db.query(BookChapter).filter(BookChapter.book_id == book.id).order_by(BookChapter.order_index).all():
        lines += ["", f"## {ch.title}", "", ch.intro or "", ch.content or ""]
        for sid in ch.story_ids or []:
            story = db.query(Story).filter(Story.id == sid).first()
            if story and story.current_version_id:
                v = db.query(StoryVersion).filter(StoryVersion.id == story.current_version_id).first()
                lines += ["", f"### {story.title or '无标题'}", "", v.content if v else ""]
    return "\n".join(lines)


def _render_pdf(db: Session, book: Book, path: Path) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont

    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    c = canvas.Canvas(str(path), pagesize=A4)
    width, height = A4
    y = height - 60

    def write_line(text: str, size: int = 11):
        nonlocal y
        if y < 60:
            c.showPage()
            y = height - 60
        c.setFont("STSong-Light", size)
        # crude wrap by character count
        for i in range(0, len(text), 42):
            if y < 60:
                c.showPage()
                y = height - 60
            c.drawString(50, y, text[i : i + 42])
            y -= size + 6

    write_line(book.title, 22)
    write_line(book.subtitle or "", 13)
    write_line(f"作者：{book.author or ''}", 11)
    for ch in db.query(BookChapter).filter(BookChapter.book_id == book.id).order_by(BookChapter.order_index).all():
        y -= 16
        write_line(ch.title, 16)
        if ch.intro:
            write_line(ch.intro)
        if ch.content:
            write_line(ch.content)
        for sid in ch.story_ids or []:
            story = db.query(Story).filter(Story.id == sid).first()
            if story and story.current_version_id:
                v = db.query(StoryVersion).filter(StoryVersion.id == story.current_version_id).first()
                if v:
                    y -= 10
                    write_line(story.title or "无标题", 13)
                    write_line(v.content)
    c.save()


@router.get("/{book_id}/export")
@router.post("/{book_id}/export")
def export(book_id: str, format: str = "markdown", user=Depends(get_current_user), db: Session = Depends(get_db)):
    if format not in ("pdf", "markdown", "json"):
        raise HTTPException(status_code=400, detail="当前支持 pdf / markdown / json；EPUB 后续版本提供")
    book = db.query(Book).filter(Book.id == book_id, Book.user_id == user.id).first()
    if not book:
        raise HTTPException(status_code=404, detail="回忆录不存在")
    out_dir = settings.upload_dir / "exports" / user.id
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{book.id}.{format}"
    if format == "markdown":
        path.write_text(_render_markdown(db, book), encoding="utf-8")
    elif format == "json":
        chapters = db.query(BookChapter).filter(BookChapter.book_id == book.id).order_by(BookChapter.order_index).all()
        path.write_text(
            json.dumps({"book": {"id": book.id, "title": book.title, "author": book.author}, "chapters": [c.__dict__ for c in chapters]}, ensure_ascii=False, default=str, indent=2),
            encoding="utf-8",
        )
    else:
        _render_pdf(db, book, path)
    job = BookExportJob(book_id=book.id, user_id=user.id, format=format, status="completed", file_path=str(path))
    db.add(job)
    book.status = "exported"
    db.commit()
    return FileResponse(str(path), filename=f"{book.title}.{format}")


@router.post("/{book_id}/qr", status_code=201)
def create_qr(book_id: str, story_id: str | None = None, user=Depends(get_current_user), db: Session = Depends(get_db)):
    book = db.query(Book).filter(Book.id == book_id, Book.user_id == user.id).first()
    if not book:
        raise HTTPException(status_code=404, detail="回忆录不存在")
    qr = BookQRCode(book_id=book.id, story_id=story_id, token=secrets.token_urlsafe(24), status="active")
    db.add(qr)
    db.commit()
    db.refresh(qr)
    return {"id": qr.id, "token": qr.token, "url": f"/public/story/{qr.token}", "status": qr.status}


@router.post("/qr/{qr_id}/revoke")
def revoke_qr(qr_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    qr = db.query(BookQRCode).filter(BookQRCode.id == qr_id).first()
    if not qr:
        raise HTTPException(status_code=404, detail="二维码不存在")
    book = db.query(Book).filter(Book.id == qr.book_id, Book.user_id == user.id).first()
    if not book:
        raise HTTPException(status_code=403, detail="无权操作")
    qr.status = "revoked"
    qr.revoked_at = utcnow()
    db.commit()
    return {"message": "二维码已撤销"}


@router.get("/public/story/{token}")
def public_story(token: str, db: Session = Depends(get_db)):
    """Stable, unpredictable public ID; permission-checked, revocable; never exposes storage paths."""
    qr = db.query(BookQRCode).filter(BookQRCode.token == token, BookQRCode.status == "active").first()
    if not qr or not qr.story_id:
        raise HTTPException(status_code=404, detail="故事页面不存在或已撤销")
    story = db.query(Story).filter(Story.id == qr.story_id, Story.visibility.in_(["family", "public"])).first()
    if not story:
        raise HTTPException(status_code=403, detail="该故事未授权公开访问")
    version = db.query(StoryVersion).filter(StoryVersion.id == story.current_version_id).first()
    return {"title": story.title, "content": version.content if version else "", "storyteller_id": story.storyteller_id}
