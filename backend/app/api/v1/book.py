"""Legacy Book: builder, chapters, exports (PDF/Markdown/JSON) & QR codes."""

from __future__ import annotations

import json
import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.config import settings
from app.core.deps import get_current_user, get_current_user_optional, get_db
from app.core.security import utcnow
from app.models.family import FamilyMember
from app.models.publishing import Book, BookChapter, BookExportJob, BookQRCode
from app.models.story import Story, StoryVersion

router = APIRouter(prefix="/book", tags=["legacy-book"])

# 公开故事页允许的可见性：family 需要登录且是家庭成员；public 才可匿名访问。
PUBLIC_VISIBILITY = {"family", "public"}


def _owned_book(db: Session, book_id: str, user_id: str) -> Book:
    """所有书籍操作先做归属校验（服务端资源级鉴权，防止 IDOR）。"""
    book = (
        db.query(Book)
        .filter(Book.id == book_id, Book.user_id == user_id, Book.deleted_at.is_(None))
        .first()
    )
    if not book:
        raise HTTPException(status_code=404, detail="回忆录不存在")
    return book


def _is_family_member(db: Session, family_id: str | None, user_id: str) -> bool:
    if not family_id:
        return False
    return (
        db.query(FamilyMember)
        .filter(
            FamilyMember.family_id == family_id,
            FamilyMember.user_id == user_id,
            FamilyMember.deleted_at.is_(None),
        )
        .first()
        is not None
    )


def _owned_story_ids(db: Session, book: Book, story_ids: list[str] | None) -> list[str]:
    """章节只能引用本人故事，避免通过导出读取他人内容。"""
    if not story_ids:
        return []
    return [
        s.id
        for s in db.query(Story)
        .filter(
            Story.id.in_(story_ids),
            Story.user_id == book.user_id,
            Story.deleted_at.is_(None),
        )
        .all()
    ]


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
    # 书籍可归属家庭空间，但必须验证当前用户确为该家庭成员（多家庭不串号）。
    if payload.family_id and not _is_family_member(db, payload.family_id, user.id):
        raise HTTPException(status_code=403, detail="不是该家庭的成员，无法在其中创建回忆录")
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
    return (
        db.query(Book)
        .filter(Book.user_id == user.id, Book.deleted_at.is_(None))
        .order_by(Book.created_at.desc())
        .all()
    )


@router.get("/{book_id}")
def get_book(book_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    book = _owned_book(db, book_id, user.id)
    chapters = (
        db.query(BookChapter)
        .filter(BookChapter.book_id == book.id)
        .order_by(BookChapter.order_index, BookChapter.created_at)
        .all()
    )
    return {"book": book, "chapters": chapters}


@router.post("/{book_id}/chapters", status_code=201)
def add_chapter(book_id: str, payload: ChapterIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    book = _owned_book(db, book_id, user.id)
    data = payload.model_dump()
    data["story_ids"] = _owned_story_ids(db, book, data.get("story_ids"))
    ch = BookChapter(book_id=book.id, **data)
    db.add(ch)
    db.commit()
    db.refresh(ch)
    return ch


@router.put("/chapters/{chapter_id}")
def update_chapter(chapter_id: str, payload: ChapterIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    ch = db.query(BookChapter).filter(BookChapter.id == chapter_id).first()
    if not ch:
        raise HTTPException(status_code=404, detail="章节不存在")
    book = _owned_book(db, ch.book_id, user.id)
    # 部分更新：前端可通过只传 order_index 实现上移/下移，不覆盖标题与正文。
    data = payload.model_dump(exclude_unset=True)
    if "story_ids" in data:
        data["story_ids"] = _owned_story_ids(db, book, data.get("story_ids"))
    for k, v in data.items():
        setattr(ch, k, v)
    db.commit()
    return ch


@router.delete("/chapters/{chapter_id}")
def delete_chapter(chapter_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    ch = db.query(BookChapter).filter(BookChapter.id == chapter_id).first()
    if not ch:
        raise HTTPException(status_code=404, detail="章节不存在")
    _owned_book(db, ch.book_id, user.id)
    db.delete(ch)
    db.commit()
    return {"message": "章节已删除"}


def _render_markdown(db: Session, book: Book) -> str:
    lines = [f"# {book.title}", "", book.subtitle or "", f"作者：{book.author or ''}", ""]
    for ch in db.query(BookChapter).filter(BookChapter.book_id == book.id).order_by(BookChapter.order_index).all():
        lines += ["", f"## {ch.title}", "", ch.intro or "", ch.content or ""]
        for sid in ch.story_ids or []:
            # 只渲染本人故事，杜绝通过构造 story_ids 读取他人内容。
            story = (
                db.query(Story)
                .filter(Story.id == sid, Story.user_id == book.user_id, Story.deleted_at.is_(None))
                .first()
            )
            if story and story.current_version_id:
                v = db.query(StoryVersion).filter(StoryVersion.id == story.current_version_id).first()
                lines += ["", f"### {story.title or '无标题'}", "", v.content if v else ""]
    return "\n".join(lines)


def _render_pdf(db: Session, book: Book, path: Path) -> None:
    """Editorial-style PDF: full-bleed cover, title page, TOC, illustrated chapters, back cover."""
    from io import BytesIO

    from PIL import Image
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.pdfgen import canvas

    from app.models.media import MediaAsset
    from app.storage import get_storage

    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    FONT = "STSong-Light"
    NAVY = colors.HexColor("#0B1730")
    GOLD = colors.HexColor("#E7B75A")
    GRAY = colors.HexColor("#5B6B85")

    c = canvas.Canvas(str(path), pagesize=A4)
    W, H = A4
    M = 54

    def read_image(asset_id: str | None, max_px: int = 1500):
        if not asset_id:
            return None
        # 媒体同样按 owner 过滤：不能借章节的 media_ids 渲染他人私有图片。
        asset = (
            db.query(MediaAsset)
            .filter(MediaAsset.id == asset_id, MediaAsset.user_id == book.user_id)
            .first()
        )
        if not asset or (asset.media_type and asset.media_type != "photo"):
            return None  # 跳过音频/视频/文档，只渲染图片
        try:
            raw = get_storage().read(asset.storage_key)
        except Exception:
            return None
        try:
            img = Image.open(BytesIO(raw))
            img.thumbnail((max_px, max_px))
            return ImageReader(img)
        except Exception:
            return ImageReader(BytesIO(raw))

    def draw_full_bleed(asset_id: str | None) -> bool:
        img = read_image(asset_id)
        if img is None:
            return False
        iw, ih = img.getSize()
        scale = max(W / iw, H / ih)
        dw, dh = iw * scale, ih * scale
        c.saveState()
        clip = c.beginPath()
        clip.rect(0, 0, W, H)
        c.clipPath(clip)
        c.drawImage(img, (W - dw) / 2, (H - dh) / 2, width=dw, height=dh)
        c.restoreState()
        return True

    state = {"y": H - M, "page": 1}

    def new_page() -> None:
        c.showPage()
        state["y"] = H - M
        state["page"] += 1
        c.setFont(FONT, 8)
        c.setFillColor(GRAY)
        c.drawRightString(W - M, 26, str(state["page"]))
        c.setFillColor(colors.black)

    def wrap(text: str, size: float, max_width: float) -> list[str]:
        c.setFont(FONT, size)
        lines: list[str] = []
        cur = ""
        for ch in (text or "").replace("\r", ""):
            if ch == "\n":
                lines.append(cur)
                cur = ""
                continue
            if pdfmetrics.stringWidth(cur + ch, FONT, size) <= max_width:
                cur += ch
            else:
                lines.append(cur)
                cur = ch
        if cur:
            lines.append(cur)
        return lines

    def para(text: str, size: float = 10.5, color=None, gap: int = 6) -> None:
        for line in wrap(text, size, W - 2 * M):
            if state["y"] < M + 18:
                new_page()
            c.setFont(FONT, size)
            c.setFillColor(color or colors.black)
            c.drawString(M, state["y"], line)
            state["y"] -= size + 6
        state["y"] -= gap
        c.setFillColor(colors.black)

    def draw_chapter_images(ids, max_height: float = 250) -> None:
        for aid in (ids or [])[:2]:
            img = read_image(aid, max_px=1200)
            if img is None:
                continue
            iw, ih = img.getSize()
            draw_w = W - 2 * M
            draw_h = draw_w * ih / iw
            if draw_h > max_height:
                draw_h = max_height
                draw_w = draw_h * iw / ih
            if state["y"] - draw_h < M + 18:
                new_page()
            c.drawImage(img, M + (W - 2 * M - draw_w) / 2, state["y"] - draw_h, width=draw_w, height=draw_h)
            state["y"] -= draw_h + 10

    chapters = db.query(BookChapter).filter(BookChapter.book_id == book.id).order_by(BookChapter.order_index).all()

    # 1) Front cover (full bleed) — generated AI cover image
    if not draw_full_bleed(book.cover_media_id):
        c.setFillColor(NAVY)
        c.rect(0, 0, W, H, fill=1, stroke=0)
        c.setFillColor(GOLD)
        c.setFont(FONT, 30)
        c.drawCentredString(W / 2, H * 0.58, book.title)
        c.setFont(FONT, 13)
        c.drawCentredString(W / 2, H * 0.52, book.subtitle or "")
    c.showPage()

    # 2) Title page
    c.setFillColor(NAVY)
    c.rect(0, H - 150, W, 150, fill=1, stroke=0)
    c.setFillColor(GOLD)
    c.setFont(FONT, 10)
    c.drawCentredString(W / 2, H - 60, "MEMOIR · 人生回忆录")
    c.setFillColor(NAVY)
    c.setFont(FONT, 28)
    c.drawCentredString(W / 2, H - 245, book.title)
    c.setFillColor(GRAY)
    c.setFont(FONT, 13)
    c.drawCentredString(W / 2, H - 285, book.subtitle or "")
    c.setFont(FONT, 11)
    c.drawCentredString(W / 2, H - 320, f"作者：{book.author or '林一'}")
    c.setStrokeColor(GOLD)
    c.setLineWidth(1.2)
    c.line(W / 2 - 60, H - 350, W / 2 + 60, H - 350)
    c.showPage()

    # 3) Table of contents
    state["y"] = H - M
    c.setFillColor(NAVY)
    c.setFont(FONT, 20)
    c.drawString(M, state["y"], "目录")
    state["y"] -= 40
    for i, ch in enumerate(chapters, 1):
        c.setFont(FONT, 12)
        c.setFillColor(NAVY)
        c.drawString(M, state["y"], f"{i:02d}  {ch.title}")
        c.setFillColor(GRAY)
        c.drawRightString(W - M, state["y"], "第 " + str(i + 2) + " 章")
        state["y"] -= 24
    c.setFillColor(colors.black)
    c.showPage()

    # 4) Chapters
    state["y"] = H - M
    c.setFont(FONT, 8)
    c.setFillColor(GRAY)
    c.drawRightString(W - M, 26, str(state["page"]))
    c.setFillColor(colors.black)
    for idx, ch in enumerate(chapters):
        if idx > 0:
            new_page()
        c.setFillColor(NAVY)
        c.setFont(FONT, 19)
        c.drawString(M, state["y"], ch.title)
        state["y"] -= 22
        c.setStrokeColor(GOLD)
        c.setLineWidth(1.2)
        c.line(M, state["y"], W - M, state["y"])
        state["y"] -= 26
        if ch.intro:
            para(ch.intro, 11, GRAY)
        if ch.content:
            para(ch.content, 10.5)
        draw_chapter_images(ch.media_ids)
        for sid in ch.story_ids or []:
            story = (
                db.query(Story)
                .filter(Story.id == sid, Story.user_id == book.user_id, Story.deleted_at.is_(None))
                .first()
            )
            if not story or not story.current_version_id:
                continue
            version = db.query(StoryVersion).filter(StoryVersion.id == story.current_version_id).first()
            if not version:
                continue
            para(story.title or "无标题", 14, NAVY)
            para(version.content, 10.5)

    # 5) Back cover (full bleed) — generated AI back cover
    c.showPage()
    back_id = (book.settings or {}).get("back_cover_media_id")
    if not draw_full_bleed(back_id):
        c.setFillColor(NAVY)
        c.rect(0, 0, W, H, fill=1, stroke=0)
        c.setFillColor(GOLD)
        c.setFont(FONT, 12)
        c.drawCentredString(W / 2, H / 2, "Your Life. Your Stories. Your Legacy.")
    c.save()


@router.get("/{book_id}/export")
@router.post("/{book_id}/export")
def export(book_id: str, format: str = "markdown", user=Depends(get_current_user), db: Session = Depends(get_db)):
    if format not in ("pdf", "markdown", "json"):
        raise HTTPException(status_code=400, detail="当前支持 pdf / markdown / json；EPUB 后续版本提供")
    book = _owned_book(db, book_id, user.id)
    out_dir = settings.upload_dir / "exports" / user.id
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{book.id}.{format}"
    if format == "markdown":
        path.write_text(_render_markdown(db, book), encoding="utf-8")
    elif format == "json":
        chapters = (
            db.query(BookChapter)
            .filter(BookChapter.book_id == book.id)
            .order_by(BookChapter.order_index)
            .all()
        )
        # 导出内容只含本人数据；file_path 等内部信息不写入响应。
        path.write_text(
            json.dumps(
                {
                    "book": {"id": book.id, "title": book.title, "author": book.author},
                    "chapters": [c.__dict__ for c in chapters],
                },
                ensure_ascii=False,
                default=str,
                indent=2,
            ),
            encoding="utf-8",
        )
    else:
        _render_pdf(db, book, path)
    job = BookExportJob(book_id=book.id, user_id=user.id, format=format, status="completed", file_path=str(path))
    db.add(job)
    book.status = "exported"
    db.commit()
    log_action("book.export", user_id=user.id, resource_type="book", resource_id=book.id, detail=format)
    return FileResponse(str(path), filename=f"{book.title}.{format}")


@router.get("/{book_id}/qr")
def list_qr(book_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """列出书籍的二维码及其状态，供前端展示与撤销（仅本人）。"""
    book = _owned_book(db, book_id, user.id)
    rows = (
        db.query(BookQRCode)
        .filter(BookQRCode.book_id == book.id)
        .order_by(BookQRCode.created_at.desc())
        .all()
    )
    return [
        {
            "id": q.id,
            "story_id": q.story_id,
            "token": q.token,
            "url": f"/public/story/{q.token}",
            "status": q.status,
            "revoked_at": q.revoked_at,
            "created_at": q.created_at,
        }
        for q in rows
    ]


@router.post("/{book_id}/qr", status_code=201)
def create_qr(book_id: str, story_id: str | None = None, user=Depends(get_current_user), db: Session = Depends(get_db)):
    book = _owned_book(db, book_id, user.id)
    if story_id:
        story = (
            db.query(Story)
            .filter(Story.id == story_id, Story.user_id == user.id, Story.deleted_at.is_(None))
            .first()
        )
        if not story:
            raise HTTPException(status_code=404, detail="故事不存在或无访问权限")
        if story.visibility not in PUBLIC_VISIBILITY:
            raise HTTPException(
                status_code=400,
                detail="私有故事不能生成公开二维码，请先将故事可见性设为 family 或 public",
            )
    qr = BookQRCode(book_id=book.id, story_id=story_id, token=secrets.token_urlsafe(24), status="active")
    db.add(qr)
    db.commit()
    db.refresh(qr)
    log_action("book.qr.create", user_id=user.id, resource_type="book", resource_id=book.id)
    # 只返回不稳定的公开 token 与相对 URL，绝不返回存储路径或 target_url。
    return {"id": qr.id, "token": qr.token, "url": f"/public/story/{qr.token}", "status": qr.status}


@router.post("/qr/{qr_id}/revoke")
def revoke_qr(qr_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    qr = db.query(BookQRCode).filter(BookQRCode.id == qr_id).first()
    if not qr:
        raise HTTPException(status_code=404, detail="二维码不存在")
    _owned_book(db, qr.book_id, user.id)
    if qr.status != "revoked":
        qr.status = "revoked"
        qr.revoked_at = str(utcnow())
        db.commit()
        log_action("book.qr.revoke", user_id=user.id, resource_type="book_qr_code", resource_id=qr.id)
    return {"message": "二维码已撤销", "status": qr.status}


@router.get("/public/story/{token}")
def public_story(
    token: str,
    user=Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """公开故事页：token active + 可见性校验；private 不可匿名访问；不暴露任何存储路径。"""
    qr = (
        db.query(BookQRCode)
        .filter(BookQRCode.token == token, BookQRCode.status == "active")
        .first()
    )
    if not qr or not qr.story_id:
        raise HTTPException(status_code=404, detail="故事页面不存在或已撤销")
    story = (
        db.query(Story)
        .filter(Story.id == qr.story_id, Story.deleted_at.is_(None))
        .first()
    )
    if not story or story.visibility not in PUBLIC_VISIBILITY:
        raise HTTPException(status_code=403, detail="该故事未授权公开访问")

    if story.visibility == "family":
        # 家庭可见 ≠ 匿名可见：必须登录，且是故事作者或家庭成员。
        allowed = user is not None and (
            user.id == story.user_id or _is_family_member(db, story.family_id, user.id)
        )
        if not allowed:
            raise HTTPException(status_code=403, detail="家庭可见故事需要登录并以家庭成员身份访问")

    version = (
        db.query(StoryVersion)
        .filter(StoryVersion.id == story.current_version_id)
        .first()
        if story.current_version_id
        else None
    )
    return {
        "title": story.title,
        "content": version.content if version else "",
        "storyteller_id": story.storyteller_id,
        "visibility": story.visibility,
    }
