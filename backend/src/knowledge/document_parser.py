"""文档解析器 — 将 docx/pptx/pdf/xlsx/md 转为 markdown 文本供 LLM 读取。"""

import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ParsedDocument:
    """解析后的文档。"""
    source_file: str
    title: str = ""
    text: str = ""
    images: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class DocumentParser:
    """统一文档解析入口。"""

    def __init__(self, assets_dir: str):
        self.assets_dir = assets_dir
        os.makedirs(assets_dir, exist_ok=True)

    def parse(self, file_path: str) -> ParsedDocument:
        """根据文件扩展名分发解析。"""
        ext = os.path.splitext(file_path)[1].lower()
        parsers = {
            ".docx": self._parse_docx,
            ".doc": self._parse_docx,
            ".pptx": self._parse_pptx,
            ".ppt": self._parse_pptx,
            ".pdf": self._parse_pdf,
            ".xlsx": self._parse_xlsx,
            ".xls": self._parse_xlsx,
            ".md": self._parse_md,
            ".txt": self._parse_md,
        }
        parser = parsers.get(ext)
        if not parser:
            # 不支持的格式，尝试作为纯文本读取
            return self._parse_md(file_path)

        try:
            return parser(file_path)
        except Exception as e:
            logger.error("解析文档失败 %s: %s", file_path, e)
            return ParsedDocument(source_file=file_path, title=os.path.basename(file_path), text=f"[解析失败: {e}]")

    def _parse_docx(self, path: str) -> ParsedDocument:
        from docx import Document
        from docx.opc.constants import RELATIONSHIP_TYPE as RT

        doc = Document(path)
        title = ""
        if doc.core_properties.title:
            title = doc.core_properties.title
        if not title:
            title = os.path.splitext(os.path.basename(path))[0]

        parts = []
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            style = para.style.name if para.style else ""
            if "Heading 1" in style:
                parts.append(f"# {text}")
            elif "Heading 2" in style:
                parts.append(f"## {text}")
            elif "Heading 3" in style:
                parts.append(f"### {text}")
            else:
                parts.append(text)

        # 提取表格
        for table in doc.tables:
            rows = []
            for row in table.rows:
                cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                rows.append("| " + " | ".join(cells) + " |")
            if rows:
                header = rows[0]
                sep = "|" + "|".join(["---"] * len(table.rows[0].cells)) + "|"
                parts.append(header)
                parts.append(sep)
                parts.extend(rows[1:])
                parts.append("")

        # 提取图片
        images = self._extract_docx_images(doc, path)

        return ParsedDocument(
            source_file=path,
            title=title,
            text="\n\n".join(parts),
            images=images,
            metadata={"pages": 1, "type": "docx"},
        )

    def _extract_docx_images(self, doc, path: str) -> list[str]:
        """从 docx 中提取图片到 assets 目录。"""
        images = []
        try:
            from docx.opc.constants import RELATIONSHIP_TYPE as RT
            import hashlib

            for rel in doc.part.rels.values():
                if "image" in rel.reltype:
                    img_data = rel.target_part.blob
                    ext = os.path.splitext(rel.target_part.partname)[1] or ".png"
                    h = hashlib.md5(img_data).hexdigest()[:8]
                    img_name = f"{os.path.splitext(os.path.basename(path))[0]}_{h}{ext}"
                    img_path = os.path.join(self.assets_dir, img_name)
                    with open(img_path, "wb") as f:
                        f.write(img_data)
                    images.append(img_path)
        except Exception as e:
            logger.warning("提取 docx 图片失败: %s", e)
        return images

    def _parse_pptx(self, path: str) -> ParsedDocument:
        from pptx import Presentation

        prs = Presentation(path)
        title = os.path.splitext(os.path.basename(path))[0]

        parts = []
        for i, slide in enumerate(prs.slides, 1):
            parts.append(f"## 幻灯片 {i}")
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for para in shape.text_frame.paragraphs:
                        text = para.text.strip()
                        if text:
                            parts.append(text)
                if shape.has_table:
                    table = shape.table
                    rows = []
                    for row in table.rows:
                        cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                        rows.append("| " + " | ".join(cells) + " |")
                    if rows:
                        header = rows[0]
                        sep = "|" + "|".join(["---"] * len(table.rows[0].cells)) + "|"
                        parts.append(header)
                        parts.append(sep)
                        parts.extend(rows[1:])
            # 备注
            if slide.has_notes_slide:
                notes = slide.notes_slide.notes_text_frame.text.strip()
                if notes:
                    parts.append(f"> 备注: {notes}")
            parts.append("")

        return ParsedDocument(
            source_file=path,
            title=title,
            text="\n\n".join(parts),
            images=[],
            metadata={"slides": len(prs.slides), "type": "pptx"},
        )

    def _parse_pdf(self, path: str) -> ParsedDocument:
        import pdfplumber

        title = os.path.splitext(os.path.basename(path))[0]
        parts = []
        total_pages = 0

        with pdfplumber.open(path) as pdf:
            total_pages = len(pdf.pages)
            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                if text:
                    parts.append(text)

                # 提取表格
                tables = page.extract_tables()
                for table in tables:
                    if not table:
                        continue
                    rows = []
                    for row in table:
                        cells = [str(c or "").strip().replace("\n", " ") for c in row]
                        rows.append("| " + " | ".join(cells) + " |")
                    if rows:
                        header = rows[0]
                        col_count = len(table[0]) if table else 0
                        sep = "|" + "|".join(["---"] * col_count) + "|"
                        parts.append(header)
                        parts.append(sep)
                        parts.extend(rows[1:])
                        parts.append("")

        return ParsedDocument(
            source_file=path,
            title=title,
            text="\n\n".join(parts),
            images=[],
            metadata={"pages": total_pages, "type": "pdf"},
        )

    def _parse_xlsx(self, path: str) -> ParsedDocument:
        from openpyxl import load_workbook

        title = os.path.splitext(os.path.basename(path))[0]
        wb = load_workbook(path, read_only=True, data_only=True)
        parts = []

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            parts.append(f"## {sheet_name}")
            for row in ws.iter_rows(values_only=True):
                cells = [str(c or "").strip() for c in row]
                if any(cells):
                    parts.append("| " + " | ".join(cells) + " |")
            # 在第一行后加分隔线
            if len(parts) > 1:
                col_count = ws.max_column or 1
                sep = "|" + "|".join(["---"] * col_count) + "|"
                # 在表头行之后插入分隔符
                header_idx = len(parts) - ws.max_row if ws.max_row else -1
                # 简化处理：直接追加
            parts.append("")

        wb.close()
        return ParsedDocument(
            source_file=path,
            title=title,
            text="\n\n".join(parts),
            images=[],
            metadata={"sheets": len(wb.sheetnames), "type": "xlsx"},
        )

    def _parse_md(self, path: str) -> ParsedDocument:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        title = os.path.splitext(os.path.basename(path))[0]
        # 尝试从第一行 # 标题 提取
        for line in text.split("\n"):
            if line.startswith("# "):
                title = line[2:].strip()
                break
        return ParsedDocument(
            source_file=path,
            title=title,
            text=text,
            images=[],
            metadata={"type": os.path.splitext(path)[1].lstrip(".")},
        )
