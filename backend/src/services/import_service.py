"""历史数据文件导入服务 — 上传 → 解析预览 → 列映射 → 校验 → 批量入库。

支持格式: .xlsx, .xls, .csv, .json
支持表格式: 宽表 (一行多参数) 和 长表 (一行一参数值)
"""

import os
import json
import logging
from datetime import datetime

import pandas as pd
from sqlalchemy import text

from src.db.engine import get_session
from src.db.models import ImportJob, TimeSeriesPoint, Parameter

logger = logging.getLogger(__name__)

# 常用时间格式预设（供前端下拉与后端解析使用）
PRESET_TIMESTAMP_FORMATS = {
    "YYYY-MM-DD HH:MM:SS": "%Y-%m-%d %H:%M:%S",
    "YYYY/MM/DD HH:MM:SS": "%Y/%m/%d %H:%M:%S",
    "YYYY年MM月DD日 HH:MM:SS": "%Y年%m月%d日 %H:%M:%S",
    "YYYY-MM-DD": "%Y-%m-%d",
    "YYYYMMDDHHMMSS": "%Y%m%d%H%M%S",
    "DD/MM/YYYY HH:MM:SS": "%d/%m/%Y %H:%M:%S",
    "MM/DD/YYYY hh:mm:ss AM/PM": "%m/%d/%Y %I:%M:%S %p",
    "Mon DD, YYYY hh:mm:ss AM/PM": "%b %d, %Y %I:%M:%S %p",
    "ISO8601": "%Y-%m-%dT%H:%M:%S",
    "ISO8601+TZ": "%Y-%m-%dT%H:%M:%S%z",
}


def get_timestamp_format_presets():
    from datetime import datetime
    now = datetime.now()
    presets = []
    for k, fmt in PRESET_TIMESTAMP_FORMATS.items():
        try:
            ex = now.strftime(fmt)
        except Exception:
            ex = ""
        presets.append({"key": k, "format": fmt, "example": ex})
    return presets


def _parse_timestamp_series(series, fmt_spec):
    """Parse timestamp pandas Series.
    fmt_spec: None | 'auto' | format-string | 'preset:<key>'
    Returns (parsed_series, success_rate)
    """
    if fmt_spec:
        # preset:key -> look up format
        if isinstance(fmt_spec, str) and fmt_spec.startswith("preset:"):
            key = fmt_spec.split("preset:", 1)[1]
            fmt = PRESET_TIMESTAMP_FORMATS.get(key)
        else:
            fmt = fmt_spec if fmt_spec != "auto" else None
        if fmt:
            parsed = pd.to_datetime(series, format=fmt, errors="coerce")
            return parsed, parsed.notna().mean()
    # Auto detect: try infer with dayfirst=True first (CN), fallback to False (US)
    parsed = pd.to_datetime(series, infer_datetime_format=True, errors="coerce", dayfirst=True)
    rate = parsed.notna().mean()
    if rate < 0.8:
        parsed2 = pd.to_datetime(series, infer_datetime_format=True, errors="coerce", dayfirst=False)
        rate2 = parsed2.notna().mean()
        if rate2 > rate:
            return parsed2, rate2
    return parsed, rate


# 上传文件暂存目录
UPLOAD_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "uploads")
)
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 支持的文件扩展名
ALLOWED_EXTENSIONS = {".xlsx", ".xls", ".csv", ".json"}


# ────────────────── 工具函数 ──────────────────

def _detect_file_type(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"不支持的文件格式: {ext}，支持: {ALLOWED_EXTENSIONS}")
    return ext.lstrip(".")


def _detect_csv_encoding(filepath: str) -> str:
    """尝试用多种编码读取 CSV 第一行。"""
    for enc in ("utf-8-sig", "utf-8", "gb18030", "gb2312", "gbk", "latin-1"):
        try:
            with open(filepath, "r", encoding=enc) as f:
                f.readline()
            return enc
        except (UnicodeDecodeError, UnicodeError):
            continue
    return "utf-8"


def _read_file(filepath: str, file_type: str, nrows: int | None = None) -> pd.DataFrame:
    """读取文件到 DataFrame。nrows 限制预览行数，加速大文件解析。"""
    if file_type in ("xlsx", "xls"):
        return pd.read_excel(filepath, engine="openpyxl" if file_type == "xlsx" else None, nrows=nrows)
    elif file_type == "csv":
        enc = _detect_csv_encoding(filepath)
        # 尝试常见分隔符
        for sep in (",", "\t", ";"):
            try:
                df = pd.read_csv(filepath, encoding=enc, sep=sep, nrows=5)
                if len(df.columns) > 1:
                    return pd.read_csv(filepath, encoding=enc, sep=sep, nrows=nrows)
            except Exception:
                continue
        return pd.read_csv(filepath, encoding=enc, nrows=nrows)
    elif file_type == "json":
        df = pd.read_json(filepath)
        if nrows:
            df = df.head(nrows)
        return df
    else:
        raise ValueError(f"未知文件类型: {file_type}")


def _fast_row_count(filepath: str, file_type: str) -> int:
    """快速获取文件总行数（不加载全部数据）。"""
    try:
        if file_type in ("xlsx", "xls"):
            import openpyxl
            wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
            ws = wb.active
            count = max(0, (ws.max_row or 1) - 1)  # 减去表头
            wb.close()
            return count
        elif file_type == "csv":
            enc = _detect_csv_encoding(filepath)
            with open(filepath, "r", encoding=enc) as f:
                return sum(1 for _ in f) - 1  # 减去表头
        elif file_type == "json":
            df = pd.read_json(filepath, nrows=1)
            # JSON 无法快速计数，需要全量读取（后续优化）
            return 0
    except Exception as e:
        logger.warning("快速行数统计失败: %s", e)
        return 0
    return 0


def _auto_detect_timestamp_column(columns: list[str]) -> str | None:
    """自动检测时间戳列名。"""
    ts_keywords = ["时间", "time", "timestamp", "datetime", "date", "日期", "时刻"]
    for col in columns:
        col_lower = str(col).lower().strip()
        if any(kw in col_lower for kw in ts_keywords):
            return col
    # 如果第一列包含日期格式的值，也猜测它
    return None


# ────────────────── 核心流程 ──────────────────

def upload_file(file_content: bytes, filename: str) -> dict:
    """上传文件，解析预览，创建 ImportJob。

    Returns: {job_id, filename, columns, preview_rows, row_count,
              detected_timestamp_column, format_hint}
    """
    file_type = _detect_file_type(filename)

    # 保存文件
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = f"{ts}_{filename}"
    filepath = os.path.join(UPLOAD_DIR, safe_name)
    with open(filepath, "wb") as f:
        f.write(file_content)

    # 解析文件（只读前 200 行用于预览，避免 openpyxl 全量解析大文件超时）
    try:
        df = _read_file(filepath, file_type, nrows=200)
    except Exception as e:
        # 解析失败也要创建 job 记录
        job = _create_job(filename, file_type, len(file_content), status="error",
                          error_message=f"文件解析失败: {e}")
        return {"job_id": job.id, "status": "error", "error_message": str(e)}

    columns = [str(c) for c in df.columns.tolist()]
    preview_rows = df.head(10).fillna("").to_dict(orient="records")
    # 把 NaN/NaT 转为字符串方便 JSON
    preview_rows = [{k: str(v) if v is not pd.NaT and not (isinstance(v, float) and pd.isna(v)) else ""
                     for k, v in row.items()} for row in preview_rows]
    # 快速获取总行数（不加载全部数据）
    row_count = _fast_row_count(filepath, file_type) or len(df)
    detected_ts_col = _auto_detect_timestamp_column(columns)

    # 猜测表格式: 如果列名中有 "参数名/参数key/parameter" 类的列，可能是长表
    long_table_keywords = ["参数", "parameter", "tag", "点名", "测点", "parameter_key", "parameter_name"]
    format_hint = "long" if any(kw in str(c).lower() for c in columns for kw in long_table_keywords) else "wide"

    job = _create_job(filename, file_type, len(file_content), status="preview", total_rows=row_count)

    return {
        "job_id": job.id,
        "filename": filename,
        "file_type": file_type,
        "columns": columns,
        "preview_rows": preview_rows,
        "row_count": row_count,
        "detected_timestamp_column": detected_ts_col,
        "format_hint": format_hint,
    }


def execute_import(job_id: int, mapping: dict) -> dict:
    """执行数据导入。

    mapping = {
        "timestamp_column": "时间",
        "timestamp_format": "%Y-%m-%d %H:%M:%S",   // 可选
        "format_type": "wide",                       // wide / long
        "unit_id": "GT-01",
        "column_map": {                              // wide: 文件列名→参数key
            "压气机进口温度": "压气机进口温度_T1",
            ...
        },
        // long 模式额外字段:
        "long_param_column": "参数名",               // long: 参数名列
        "long_value_column": "值",                   // long: 值列
    }
    """
    with get_session() as session:
        job = session.query(ImportJob).filter(ImportJob.id == job_id).first()
        if not job:
            raise ValueError(f"导入任务不存在: {job_id}")
        if job.status not in ("preview", "pending", "completed", "error"):
            raise ValueError(f"任务状态不允许导入: {job.status}")

        # 更新 job 状态
        job.status = "parsing"
        job.format_type = mapping.get("format_type", "wide")
        job.unit_id = mapping.get("unit_id", "GT-01")
        job.column_mapping = json.dumps(mapping, ensure_ascii=False)
        job.started_at = datetime.now()
        session.commit()

    try:
        # 重新读取文件
        filepath = _find_upload_file(job_id, job.filename)
        df = _read_file(filepath, job.file_type)

        # 解析时间戳列（支持 auto / preset:<key> / 自定义 strftime）
        ts_col = mapping["timestamp_column"]
        ts_fmt = mapping.get("timestamp_format")
        parsed_ts, rate = _parse_timestamp_series(df[ts_col], ts_fmt or "auto")
        if rate < 0.5:
            logger.warning("解析时间戳成功率低: %.2f, 尝试使用宽松解析", rate)
        df[ts_col] = parsed_ts
        df = df.dropna(subset=[ts_col])

        # 获取参数 normal range 用于校验
        param_ranges = _get_param_ranges()

        if mapping.get("format_type", "wide") == "wide":
            records = _process_wide(df, ts_col, mapping.get("column_map", {}),
                                    mapping.get("unit_id", "GT-01"), param_ranges)
        else:
            records = _process_long(df, ts_col, mapping, param_ranges)

        # 批量入库
        _bulk_insert(records)

        # 更新 job
        with get_session() as session:
            job = session.query(ImportJob).filter(ImportJob.id == job_id).first()
            job.status = "completed"
            job.imported_rows = len(records)
            job.skipped_rows = len(df) * len(mapping.get("column_map", {})) - len(records) if mapping.get("format_type") == "wide" else len(df) - len(records)
            job.completed_at = datetime.now()
            session.commit()

        return {
            "job_id": job_id,
            "status": "completed",
            "imported_rows": len(records),
        }

    except Exception as e:
        logger.exception("导入失败 job_id=%d", job_id)
        with get_session() as session:
            job = session.query(ImportJob).filter(ImportJob.id == job_id).first()
            if job:
                job.status = "error"
                job.error_message = str(e)
                job.completed_at = datetime.now()
                session.commit()
        return {"job_id": job_id, "status": "error", "error_message": str(e)}


def get_job_preview(job_id: int) -> dict | None:
    """重新读取已上传文件，返回列预览数据（用于从历史记录恢复列映射配置）。"""
    with get_session() as session:
        job = session.query(ImportJob).filter(ImportJob.id == job_id).first()
        if not job:
            return None
        job_dict = job.to_dict()

    filepath = _find_upload_file(job_id, job.filename)
    if not filepath or not os.path.exists(filepath):
        return None

    try:
        df = _read_file(filepath, job.file_type, nrows=200)
    except Exception as e:
        logger.warning("重新读取文件失败 job_id=%d: %s", job_id, e)
        return None

    columns = [str(c) for c in df.columns.tolist()]
    preview_rows = df.head(10).fillna("").to_dict(orient="records")
    preview_rows = [{k: str(v) if v is not pd.NaT and not (isinstance(v, float) and pd.isna(v)) else ""
                     for k, v in row.items()} for row in preview_rows]
    detected_ts_col = _auto_detect_timestamp_column(columns)
    row_count = _fast_row_count(filepath, job.file_type) or len(df)
    long_table_keywords = ["参数", "parameter", "tag", "点名", "测点", "parameter_key", "parameter_name"]
    format_hint = "long" if any(kw in str(c).lower() for c in columns for kw in long_table_keywords) else "wide"

    return {
        "job_id": job_id,
        "filename": job.filename,
        "file_type": job.file_type,
        "columns": columns,
        "preview_rows": preview_rows,
        "row_count": row_count,
        "detected_timestamp_column": detected_ts_col,
        "format_hint": format_hint,
    }


def get_job_status(job_id: int) -> dict | None:
    """查询导入任务状态。"""
    with get_session() as session:
        job = session.query(ImportJob).filter(ImportJob.id == job_id).first()
        return job.to_dict() if job else None


def list_jobs() -> list[dict]:
    """列出所有导入任务。"""
    with get_session() as session:
        jobs = session.query(ImportJob).order_by(ImportJob.id.desc()).limit(100).all()
        return [j.to_dict() for j in jobs]


def delete_job(job_id: int) -> dict:
    """删除导入任务及其关联数据。"""
    with get_session() as session:
        job = session.query(ImportJob).filter(ImportJob.id == job_id).first()
        if not job:
            return {"success": False, "message": "任务不存在"}

        # 删除关联的时序数据（通过 source 标记）
        source_tag = f"import:{job_id}"
        session.query(TimeSeriesPoint).filter(TimeSeriesPoint.source == source_tag).delete()
        session.delete(job)
        session.commit()

        # 删除上传文件
        filepath = _find_upload_file(job_id, job.filename)
        if filepath and os.path.exists(filepath):
            os.remove(filepath)

        return {"success": True, "message": f"已删除任务 {job_id} 及其关联数据"}


# ────────────────── 内部函数 ──────────────────

def _create_job(filename: str, file_type: str, file_size: int,
                status: str = "pending", total_rows: int = 0,
                error_message: str = None) -> ImportJob:
    with get_session() as session:
        job = ImportJob(
            filename=filename,
            file_type=file_type,
            file_size=file_size,
            status=status,
            total_rows=total_rows,
            error_message=error_message,
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        return job


def _find_upload_file(job_id: int, filename: str) -> str | None:
    """查找上传文件（按前缀匹配 job_id 相关文件）。"""
    for f in os.listdir(UPLOAD_DIR):
        if filename in f:
            return os.path.join(UPLOAD_DIR, f)
    return None


def _get_param_ranges() -> dict[str, tuple[float | None, float | None]]:
    """获取所有参数的 normal_range，用于校验。"""
    with get_session() as session:
        params = session.query(Parameter).all()
        return {p.key: (p.normal_min, p.normal_max) for p in params}


def _process_wide(df: pd.DataFrame, ts_col: str, column_map: dict,
                   unit_id: str, param_ranges: dict) -> list[dict]:
    """处理宽表: 一行一个时间戳，多列为不同参数。"""
    records = []
    source_tag = ""  # 先不标记，等 bulk_insert 时用

    for _, row in df.iterrows():
        ts = row[ts_col]
        if pd.isna(ts):
            continue
        ts_val = ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts

        for file_col, param_key in column_map.items():
            if not param_key or param_key == "skip":
                continue
            val = row.get(file_col)
            if val is None or (isinstance(val, float) and pd.isna(val)):
                continue
            try:
                num_val = float(val)
            except (ValueError, TypeError):
                continue

            # 范围校验
            rng = param_ranges.get(param_key)
            if rng and rng[0] is not None and rng[1] is not None:
                if num_val < rng[0] or num_val > rng[1]:
                    continue  # 跳过超范围值

            records.append({
                "timestamp": ts_val,
                "unit_id": unit_id,
                "parameter_key": param_key,
                "value": num_val,
                "quality": "good",
                "source": "import",  # 会在 bulk_insert 中追加 job_id
            })

    return records


def _process_long(df: pd.DataFrame, ts_col: str, mapping: dict,
                   param_ranges: dict) -> list[dict]:
    """处理长表: 每行一个 (时间戳, 参数名, 值)。"""
    param_col = mapping.get("long_param_column", "")
    value_col = mapping.get("long_value_column", "")
    unit_id = mapping.get("unit_id", "GT-01")

    if not param_col or not value_col:
        raise ValueError("长表模式需要指定参数名列和值列")

    records = []
    for _, row in df.iterrows():
        ts = row[ts_col]
        if pd.isna(ts):
            continue
        ts_val = ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts

        param_name = str(row.get(param_col, "")).strip()
        if not param_name:
            continue
        # 尝试通过名称或 key 匹配参数
        param_key = _resolve_param_key(param_name)
        if not param_key:
            continue

        val = row.get(value_col)
        if val is None or (isinstance(val, float) and pd.isna(val)):
            continue
        try:
            num_val = float(val)
        except (ValueError, TypeError):
            continue

        rng = param_ranges.get(param_key)
        if rng and rng[0] is not None and rng[1] is not None:
            if num_val < rng[0] or num_val > rng[1]:
                continue

        records.append({
            "timestamp": ts_val,
            "unit_id": unit_id,
            "parameter_key": param_key,
            "value": num_val,
            "quality": "good",
            "source": "import",
        })

    return records


def _resolve_param_key(name_or_key: str) -> str | None:
    """通过名称或 key 查找参数的 key。"""
    with get_session() as session:
        # 先精确匹配 key
        p = session.query(Parameter).filter(Parameter.key == name_or_key).first()
        if p:
            return p.key
        # 再模糊匹配 name
        p = session.query(Parameter).filter(Parameter.name == name_or_key).first()
        if p:
            return p.key
        # 包含匹配
        p = session.query(Parameter).filter(Parameter.name.contains(name_or_key)).first()
        if p:
            return p.key
        return None


def _bulk_insert(records: list[dict], batch_size: int = 5000):
    """批量插入时序数据。"""
    if not records:
        return

    with get_session() as session:
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            objects = [TimeSeriesPoint(**r) for r in batch]
            session.bulk_save_objects(objects)
            session.commit()  # 每批提交一次
        logger.info("批量插入完成: %d 条记录", len(records))
