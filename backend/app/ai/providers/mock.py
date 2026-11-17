"""Deterministic offline Mock provider.

This is NOT a fake 'AI service connected' claim: it never calls any network and
returns deterministic, input-derived output so the whole product loop can be
developed and tested without API keys. Set AI_PROVIDER / ASR_PROVIDER to a real
adapter and provide keys to enable genuine model calls.
"""

from __future__ import annotations

import hashlib
import re
import time

from app.ai.providers.base import ASRProvider, GenerationResult, LLMProvider


def _hash_unit(text: str, n: int = 8) -> float:
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


class MockLLM(LLMProvider):
    name = "mock"

    def generate(
        self,
        system: str,
        user: str,
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1500,
        json_mode: bool = False,
    ) -> GenerationResult:
        start = time.time()
        prompt_version = re.search(r"PROMPT_VERSION:\s*(\S+)", system)
        pv = prompt_version.group(1) if prompt_version else "mock-v1"

        if json_mode:
            return GenerationResult(
                text=self._json_response(user),
                provider=self.name,
                model=model or "mock-json-v1",
                prompt_version=pv,
                latency_ms=int((time.time() - start) * 1000),
            )

        mode = "story"
        m = re.search(r"OUTPUT_MODE:\s*(\w+)", system)
        if m:
            mode = m.group(1)
        text = self._story_response(user, mode)
        return GenerationResult(
            text=text,
            provider=self.name,
            model=model or "mock-story-v1",
            prompt_version=pv,
            latency_ms=int((time.time() - start) * 1000),
        )

    @staticmethod
    def _clean_lines(user: str) -> list[str]:
        lines = []
        for raw in user.splitlines():
            s = raw.strip()
            if not s or s.startswith("讲述内容") or s.startswith("已知事实") or s.startswith("以下"):
                continue
            s = re.sub(r"^[\d\-•.、]+", "", s).strip()
            if len(s) >= 2:
                lines.append(s)
        return lines[:8]

    def _story_response(self, user: str, mode: str) -> str:
        lines = self._clean_lines(user)
        if not lines:
            return "（尚无足够的原始讲述内容，无法生成故事。请先完成录音或回答访谈问题。）"
        subject = lines[0]
        support = lines[1:4]
        lead = {
            "transcript": "【逐字稿】\n",
            "clean": "【清理版】\n",
            "first_person": "【第一人称】\n",
            "third_person": "【第三人称】\n",
            "literary": "【文学版】\n",
            "concise": "【精简版】\n",
            "documentary": "【纪实版】\n",
        }.get(mode, "【故事】\n")

        if mode in ("third_person", "documentary"):
            body = f"这段回忆围绕「{subject}」展开。" + (
                "讲述者提到，" + "；".join(support) + "。" if support else ""
            )
        elif mode == "concise":
            body = f"{subject}。" + ("".join(s[:20] + "。" for s in support))
        elif mode == "literary":
            body = f"记忆像一条缓慢的河，把「{subject}」带到眼前。" + (
                "那些日子里，" + "，".join(support) + "。" if support else ""
            )
        elif mode in ("transcript", "clean"):
            body = "\n".join(lines)
        else:
            body = f"我记得「{subject}」。" + ("".join(s + "。" for s in support))

        tail = (
            "\n\n【待确认】以下细节来自原始讲述，请核对后再发布："
            + "、".join(support[:2])
            if support
            else ""
        )
        return lead + body + tail

    def _json_response(self, user: str) -> str:
        """Structured extraction/follow-up used by fact extraction & interviewer."""
        if "follow_up" in user or "追问" in user:
            return (
                '{"follow_up":"能再多讲一点当时的细节吗？比如那是在什么时候、和谁在一起？",'
                '"reason":"信息较少，需要补充时间/人物/地点"}'
            )
        facts = {
            "time": [x for x in ("小时候", "童年", "少年", "那年", "去年", "大学", "中学") if x in user],
            "person": [x for x in ("父亲", "母亲", "爸爸", "妈妈", "祖父", "朋友", "妻子", "丈夫") if x in user],
            "place": [x for x in ("北京", "什刹海", "故宫", "学校", "家") if x in user],
            "event": [],
            "emotion": [x for x in ("快乐", "怀念", "难过", "开心", "难忘") if x in user],
        }
        import json
        return json.dumps({"facts": facts}, ensure_ascii=False)

    def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        # deterministic 16-dim bag-of-codepoints embedding (good enough for mock RAG)
        out = []
        for text in texts:
            vec = [0.0] * 16
            for ch in text:
                vec[ord(ch) % 16] += 1.0
            norm = sum(v * v for v in vec) ** 0.5 or 1.0
            out.append([round(v / norm, 6) for v in vec])
        return out


class MockASR(ASRProvider):
    name = "mock"

    def transcribe(self, data: bytes, filename: str, mime_type: str, *, language: str | None = None) -> tuple[str, dict]:
        # No real speech recognition offline. Produces a transparent, clearly-marked
        # placeholder so the pipeline is testable; never presented as a real transcript.
        text = (
            "【离线 Mock 转录：未接入真实语音识别服务】\n"
            "这是一个由 Mock ASR 生成的占位逐字稿，仅用于开发与测试流程。"
            "配置 ASR_PROVIDER 与相应密钥后将返回真实转录文本。"
        )
        return text, {"provider": "mock", "bytes": len(data), "filename": filename, "language": language}
