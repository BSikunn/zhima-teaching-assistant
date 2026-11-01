from pathlib import Path
from zipfile import ZipFile, BadZipFile
import re

SUPPORTED = {".pdf", ".pptx", ".docx", ".txt", ".md", ".srt", ".vtt"}


def extract_document(path: Path, use_llamaindex: bool = False) -> list[dict]:
    extension = path.suffix.lower()
    records = []
    if extension in {".pptx", ".docx"}:
        with ZipFile(path) as archive:
            info = archive.infolist()
            if len(info) > 10000 or sum(i.file_size for i in info) > 100 * 1024 * 1024:
                raise ValueError("文档解压后过大，请拆分文件")
    if extension == ".pdf":
        import pymupdf
        with pymupdf.open(path) as doc:
            if len(doc) > 500:
                raise ValueError("PDF 超过 500 页，请拆分上传")
            for i, page in enumerate(doc):
                records.append({"text": page.get_text(), "location": f"第 {i + 1} 页"})
    elif extension == ".pptx":
        from pptx import Presentation
        for i, slide in enumerate(Presentation(str(path)).slides):
            texts = []
            for shape in slide.shapes:
                if shape.has_text_frame:
                    texts.append(shape.text)
                if shape.has_table:
                    texts.extend(" | ".join(cell.text for cell in row.cells) for row in shape.table.rows)
            records.append({"text": "\n".join(texts), "location": f"第 {i + 1} 页"})
    elif extension == ".docx":
        from docx import Document
        doc = Document(str(path))
        records.extend({"text": p.text, "location": f"第 {i + 1} 段"} for i, p in enumerate(doc.paragraphs))
        for i, table in enumerate(doc.tables):
            records.append({"text": "\n".join(" | ".join(c.text for c in r.cells) for r in table.rows), "location": f"表格 {i + 1}"})
    else:
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("gb18030")
        if extension in {".srt", ".vtt"}:
            text = text.replace("\r\n", "\n")
            pattern = r"(?m)^(\d{1,2}:\d{2}(?::\d{2})?[,.]\d{3})\s+-->\s+(\d{1,2}:\d{2}(?::\d{2})?[,.]\d{3})[^\n]*\n(.*?)(?=\n\s*\n|\Z)"
            records.extend({"text": re.sub(r"<[^>]+>", "", match.group(3)).strip(),
                            "location": f"{match.group(1)} → {match.group(2)}"}
                           for match in re.finditer(pattern, text, re.S))
        else:
            records.extend({"text": part, "location": f"第 {i + 1} 段"} for i, part in enumerate(text.split("\n\n")))
    if sum(len(r["text"]) for r in records) > 2_000_000:
        raise ValueError("提取的文本过长，请拆分上传")
    chunks = []
    splitter = None
    if use_llamaindex:
        from llama_index.core.node_parser import SentenceSplitter
        # Native LlamaIndex overlap/recursive splitting with explicit Chinese sentence
        # boundaries. Character budgets avoid hidden NLTK/tiktoken downloads offline.
        splitter = SentenceSplitter(chunk_size=700, chunk_overlap=50, tokenizer=list,
            chunking_tokenizer_fn=lambda value: re.findall(r"[^。！？!?\n]+[。！？!?\n]?|[。！？!?\n]", value))
    for record in records:
        text = record["text"].strip()
        parts = splitter.split_text(text) if splitter else [text[offset:offset + 700] for offset in range(0, len(text), 650)]
        for part in parts:
            if part.strip():
                chunks.append({"text": part, "location": record["location"]})
    if not chunks:
        raise ValueError("未提取到文字。扫描图片需先进行 OCR；首版不自动识别图片。")
    return chunks
