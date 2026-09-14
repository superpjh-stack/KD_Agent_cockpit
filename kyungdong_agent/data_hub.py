from __future__ import annotations

import os
import sqlite3
import json
import re
from pathlib import Path
from typing import Any


class KyungdongRepository:
    """경동글로벌텍 검증용 SQLite Data Hub. 모든 레코드는 가상 데모 데이터다."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        schema = """
        CREATE TABLE IF NOT EXISTS projects (
          project_id TEXT PRIMARY KEY, customer TEXT, industry TEXT, equipment_type TEXT,
          order_amount_mkr REAL, quote_date TEXT, due_date TEXT, status TEXT, progress_pct REAL
        );
        CREATE TABLE IF NOT EXISTS designs (
          project_id TEXT, drawing_no TEXT, revision TEXT, bom_items INTEGER,
          fem_status TEXT, change_no TEXT, change_status TEXT
        );
        CREATE TABLE IF NOT EXISTS materials (
          material_lot TEXT PRIMARY KEY, project_id TEXT, material_code TEXT, specification TEXT,
          thickness_mm REAL, quantity REAL, unit TEXT, supplier TEXT, mtc_status TEXT,
          barcode TEXT, location TEXT, stock_status TEXT
        );
        CREATE TABLE IF NOT EXISTS incoming_inspections (
          inspection_id TEXT PRIMARY KEY, material_lot TEXT, inspection_date TEXT,
          dimension_required_mm REAL, dimension_measured_mm REAL,
          thickness_required_mm REAL, thickness_measured_mm REAL,
          result TEXT, document_attached INTEGER, note TEXT
        );
        CREATE TABLE IF NOT EXISTS operations (
          operation_id TEXT PRIMARY KEY, project_id TEXT, process TEXT,
          plan_hours REAL, actual_hours REAL, sourcing TEXT, status TEXT, due_date TEXT
        );
        CREATE TABLE IF NOT EXISTS equipment_readings (
          reading_id TEXT PRIMARY KEY, project_id TEXT, equipment TEXT, measured_at TEXT,
          metric TEXT, value REAL, unit TEXT, limit_value REAL, status TEXT
        );
        CREATE TABLE IF NOT EXISTS quote_predictions (
          project_id TEXT PRIMARY KEY, predicted_cost_mkr REAL, predicted_lead_days INTEGER,
          margin_pct REAL, risk_score REAL, similar_project TEXT, model_status TEXT
        );
        CREATE TABLE IF NOT EXISTS purchase_orders (
          po_no TEXT PRIMARY KEY, project_id TEXT, supplier TEXT, material_code TEXT,
          promised_date TEXT, expected_date TEXT, delay_days INTEGER, risk TEXT, alternative TEXT
        );
        CREATE TABLE IF NOT EXISTS fat_tests (
          test_id TEXT PRIMARY KEY, project_id TEXT, test_item TEXT, measured_value REAL,
          unit TEXT, limit_text TEXT, result TEXT, failure_pattern TEXT, resolution TEXT
        );
        CREATE TABLE IF NOT EXISTS claims (
          claim_id TEXT PRIMARY KEY, project_id TEXT, category TEXT, description TEXT,
          status TEXT, root_cause TEXT, corrective_action TEXT
        );
        """
        with self._connect() as connection:
            connection.executescript(schema)
            if connection.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 0:
                self._seed(connection)
            self._initialize_knowledge(connection)

    @staticmethod
    def _initialize_knowledge(connection: sqlite3.Connection) -> None:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS knowledge_documents (
                document_id TEXT PRIMARY KEY, filename TEXT, content TEXT,
                source TEXT, status TEXT
            );
            CREATE TABLE IF NOT EXISTS rules (
                rule_id TEXT PRIMARY KEY, name TEXT, source_table TEXT,
                condition TEXT, owner TEXT, action TEXT, source_document TEXT,
                revision TEXT, status TEXT
            );
            CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT);
        """)
        directory = Path(__file__).resolve().parent.parent / "sample_docs" / "knowledge"
        for path in sorted(directory.glob("*.md")):
            connection.execute(
                "INSERT OR IGNORE INTO knowledge_documents VALUES (?, ?, ?, ?, ?)",
                (path.stem.split("_")[0], path.name, path.read_text(), "로컬 샘플", "로컬 검색 가능"),
            )
        rules_path = directory / "rules.json"
        if rules_path.exists():
            for rule in json.loads(rules_path.read_text()):
                connection.execute("INSERT OR IGNORE INTO rules VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    tuple(rule[key] for key in (
                        "rule_id", "name", "source_table", "condition", "owner", "action",
                        "source_document", "revision", "status")))

    def knowledge_documents(self) -> list[dict[str, Any]]:
        return self._query("SELECT * FROM knowledge_documents ORDER BY document_id")

    def search_knowledge(self, query: str) -> list[dict[str, Any]]:
        # Local lexical retrieval: Korean bigrams tolerate particles and spacing.
        words = re.findall(r"[가-힣a-zA-Z0-9]+", query.lower())
        terms = set(words + [word[i:i+2] for word in words for i in range(len(word)-1)])
        terms = {term for term in terms if len(term) >= 2}
        matches = []
        for doc in self.knowledge_documents():
            content = doc["content"] or ""
            searchable = (doc["filename"] + " " + content).lower()
            score = sum(term in searchable for term in terms)
            if score and content:
                matches.append({"filename": doc["filename"], "document_id": doc["document_id"],
                                "text": content, "match_count": score, "source": doc["source"]})
        return sorted(matches, key=lambda item: (-item["match_count"], item["filename"]))[:5]

    def get_rules(self) -> list[dict[str, Any]]:
        return self._query("SELECT * FROM rules ORDER BY rule_id")

    def rule_records(self, table: str, project_id: str | None = None) -> list[dict[str, Any]]:
        from .rules import RECORD_KEYS
        if table not in RECORD_KEYS:
            raise ValueError("룰 평가에 허용되지 않은 테이블입니다.")
        if table == "incoming_inspections":
            sql = "SELECT i.*, m.project_id FROM incoming_inspections i LEFT JOIN materials m ON i.material_lot=m.material_lot"
            if project_id:
                sql += " WHERE m.project_id=?"
            sql += " ORDER BY i.inspection_id"
        else:
            sql = f"SELECT * FROM {table}"
            if project_id:
                sql += " WHERE project_id=?"
            sql += f" ORDER BY {RECORD_KEYS[table]}"
        return self._query(sql, (project_id,) if project_id else ())

    def evaluate_rules(self, project_id: str | None = None, as_of: str | None = None) -> dict[str, Any]:
        from .rules import evaluate_rules
        return evaluate_rules(self, project_id, as_of)

    def setting(self, key: str) -> str | None:
        rows = self._query("SELECT value FROM app_settings WHERE key=?", (key,))
        return rows[0]["value"] if rows else None

    def save_setting(self, key: str, value: str) -> None:
        with self._connect() as connection:
            connection.execute("INSERT OR REPLACE INTO app_settings VALUES (?, ?)", (key, value))

    def save_uploaded_document(self, file_id: str, filename: str, content: str | None) -> None:
        with self._connect() as connection:
            connection.execute("INSERT OR REPLACE INTO knowledge_documents VALUES (?, ?, ?, ?, ?)",
                (file_id, filename, content, "업로드 문서", "File Search 인덱싱 완료"))

    @staticmethod
    def _seed(connection: sqlite3.Connection) -> None:
        connection.executemany("INSERT INTO projects VALUES (?,?,?,?,?,?,?,?,?)", [
            ("KGT-26001", "A화학", "정밀화학", "교반기", 180.0, "2026-06-02", "2026-09-18", "FAT 준비", 82),
            ("KGT-26002", "B소재", "이차전지 소재", "진공건조기", 320.0, "2026-07-12", "2026-10-30", "용접·조립", 58),
            ("KGT-26003", "C제약", "제약", "반응기", 245.0, "2026-08-01", "2026-11-20", "자재 조달", 31),
        ])
        connection.executemany("INSERT INTO designs VALUES (?,?,?,?,?,?,?)", [
            ("KGT-26001", "AGT-26001-GA", "C", 126, "완료", "ECO-26001-02", "승인"),
            ("KGT-26002", "VD-26002-GA", "B", 214, "검토중", "ECR-26002-03", "고객 승인대기"),
            ("KGT-26003", "RCT-26003-GA", "A", 168, "예정", "-", "변경 없음"),
        ])
        connection.executemany("INSERT INTO materials VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", [
            ("ML-260901", "KGT-26001", "SUS316L-PL", "SUS316L Plate", 12.0, 4, "EA", "한빛금속", "확인", "BC-ML-260901", "A-01", "정상"),
            ("ML-260902", "KGT-26002", "SUS304-PL", "SUS304 Plate", 16.0, 2, "EA", "대한스틸", "확인", "BC-ML-260902", "검사대기", "입고검사 보류"),
            ("ML-260903", "KGT-26003", "SUS316L-PIPE", "SUS316L Sch40", 3.0, 12, "M", "세진배관", "미첨부", "BC-ML-260903", "격리구역", "문서 미비"),
            ("ML-260904", "KGT-26002", "SEAL-PTFE", "PTFE Seal", 4.0, 1, "SET", "정밀씰", "해당없음", "BC-ML-260904", "B-03", "부족"),
        ])
        connection.executemany("INSERT INTO incoming_inspections VALUES (?,?,?,?,?,?,?,?,?,?)", [
            ("IN-260901", "ML-260901", "2026-09-01", 2000, 2000.5, 12.0, 12.1, "합격", 1, "MTC 및 거래명세서 확인"),
            ("IN-260902", "ML-260902", "2026-09-02", 2400, 2402.8, 16.0, 15.6, "보류", 1, "치수·두께 공차 재확인 필요"),
            ("IN-260903", "ML-260903", "2026-09-03", 6000, 5999.0, 3.0, 3.0, "보류", 0, "MTC/발주서 스캔본 미연결"),
        ])
        connection.executemany("INSERT INTO operations VALUES (?,?,?,?,?,?,?,?)", [
            ("OP-001", "KGT-26001", "레이저커팅", 8, 7.5, "내재화", "완료", "2026-08-05"),
            ("OP-002", "KGT-26001", "포밍", 20, 22, "사내", "완료", "2026-08-10"),
            ("OP-003", "KGT-26001", "용접", 44, 49, "사내", "완료", "2026-08-28"),
            ("OP-004", "KGT-26002", "레이저커팅", 15, 14, "내재화", "완료", "2026-08-22"),
            ("OP-005", "KGT-26002", "용접·조립", 96, 61, "사내", "진행", "2026-09-15"),
            ("OP-006", "KGT-26003", "특수표면처리", 30, 0, "외주", "발주 지연", "2026-09-25"),
        ])
        connection.executemany("INSERT INTO equipment_readings VALUES (?,?,?,?,?,?,?,?,?)", [
            ("ER-001", "KGT-26001", "교반기 시운전대", "2026-09-03 09:10", "회전속도", 118, "rpm", 120, "정상"),
            ("ER-002", "KGT-26001", "교반기 시운전대", "2026-09-03 09:10", "진동", 5.1, "mm/s", 4.5, "주의"),
            ("ER-003", "KGT-26002", "진공시험기", "2026-09-03 10:20", "진공도", -91.2, "kPa", -90, "정상"),
            ("ER-004", "KGT-26002", "용접부 예열", "2026-09-03 10:30", "온도", 142, "°C", 150, "정상"),
        ])
        connection.executemany("INSERT INTO quote_predictions VALUES (?,?,?,?,?,?,?)", [
            ("KGT-26001", 151.0, 82, 16.1, 0.22, "KGT-25014", "시제품 데모·미검증"),
            ("KGT-26002", 292.0, 104, 8.8, 0.68, "KGT-25008", "시제품 데모·미검증"),
            ("KGT-26003", 216.0, 91, 11.8, 0.47, "KGT-25021", "시제품 데모·미검증"),
        ])
        connection.executemany("INSERT INTO purchase_orders VALUES (?,?,?,?,?,?,?, ?,?)", [
            ("PO-26088", "KGT-26002", "정밀씰", "SEAL-PTFE", "2026-09-06", "2026-09-11", 5, "높음", "동일 사양 후보: 대성씰 / 승인 필요"),
            ("PO-26091", "KGT-26003", "세진배관", "SUS316L-PIPE", "2026-09-03", "2026-09-03", 0, "중간", "MTC 수령 전 사용 금지"),
            ("PO-26093", "KGT-26003", "코팅테크", "SURFACE-SPECIAL", "2026-09-20", "2026-09-27", 7, "높음", "대체 외주처 기술검토 필요"),
        ])
        connection.executemany("INSERT INTO fat_tests VALUES (?,?,?,?,?,?,?,?,?)", [
            ("FAT-001", "KGT-26001", "무부하 진동", 5.1, "mm/s", "≤ 4.5 (데모 기준)", "불합격", "축정렬/베어링 체결 반복 패턴", "재정렬 후 재시험 예정"),
            ("FAT-002", "KGT-26001", "회전속도", 118, "rpm", "120±5 (데모 기준)", "합격", "-", "-"),
            ("FAT-003", "KGT-26002", "진공 유지", -91.2, "kPa", "≤ -90 (데모 기준)", "합격", "-", "-"),
        ])
        connection.executemany("INSERT INTO claims VALUES (?,?,?,?,?,?,?)", [
            ("CLM-26001", "KGT-26001", "진동", "고객 입회 전 시운전 진동 상한 초과", "조치중", "축정렬 편차 추정", "레이저 정렬 및 체결 토크 재검증"),
            ("CLM-25014", "KGT-25014", "씰 누설", "설치 2개월 후 미세 누설", "종결", "씰 재질 선정 부적합", "견적·설계 체크리스트에 유체 적합성 추가"),
        ])

    @staticmethod
    def _dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
        return [dict(row) for row in rows]

    def _query(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self._connect() as connection:
            return self._dicts(connection.execute(sql, params).fetchall())

    # Only these business tables are exposed by the read-only UI browser.
    TABLE_LABELS = {
        "operations": "공정 실적", "materials": "자재·재고",
        "incoming_inspections": "입고검사", "designs": "설계·도면",
        "purchase_orders": "구매·발주", "fat_tests": "FAT·품질검사",
        "equipment_readings": "설비 측정", "quote_predictions": "견적 예측",
        "claims": "클레임", "projects": "프로젝트", "rules": "판정 룰",
    }

    def table_inventory(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            existing = {row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
            return [
                {"table": name, "label": label, "exists": name in existing,
                 "count": connection.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
                 if name in existing else 0}
                for name, label in self.TABLE_LABELS.items()
            ]

    def table_records(self, table: str, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        if table not in self.TABLE_LABELS:
            raise ValueError("조회할 수 없는 테이블입니다.")
        if not 1 <= limit <= 100 or offset < 0:
            raise ValueError("조회 범위가 올바르지 않습니다.")
        with self._connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
            if not exists:
                return []
            # Stable paging uses the table's declared columns; identifiers come from SQLite.
            columns = connection.execute(f'PRAGMA table_info("{table}")').fetchall()
            order = ", ".join('"' + row[1].replace('"', '""') + '"' for row in columns)
            return self._dicts(connection.execute(
                f'SELECT * FROM "{table}" ORDER BY {order} LIMIT ? OFFSET ?', (limit, offset)
            ).fetchall())

    def dashboard(self) -> dict[str, Any]:
        with self._connect() as connection:
            projects = connection.execute("SELECT COUNT(*) FROM projects WHERE status != '완료'").fetchone()[0]
            material_issues = connection.execute("SELECT COUNT(*) FROM materials WHERE stock_status != '정상'").fetchone()[0]
            po_risks = connection.execute("SELECT COUNT(*) FROM purchase_orders WHERE risk = '높음'").fetchone()[0]
            fat_failures = connection.execute("SELECT COUNT(*) FROM fat_tests WHERE result = '불합격'").fetchone()[0]
        return {
            "active_projects": projects,
            "material_issues": material_issues,
            "po_risks": po_risks,
            "fat_failures": fat_failures,
            "confirmed_avg_lead_days": 90,
            "confirmed_annual_units": 50,
            "laser_before_days": 4,
            "laser_after_days": 1,
        }

    def projects(self, project_id: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM projects"
        return self._query(sql + (" WHERE project_id = ?" if project_id else "") + " ORDER BY due_date", (project_id,) if project_id else ())

    def project_summary(self, project_id: str | None = None) -> dict[str, Any]:
        projects = self.projects(project_id)
        ids = [row["project_id"] for row in projects]
        if not ids:
            return {"projects": [], "message": "프로젝트를 찾지 못했습니다."}
        placeholders = ",".join("?" for _ in ids)
        return {
            "projects": projects,
            "designs": self._query(f"SELECT * FROM designs WHERE project_id IN ({placeholders})", tuple(ids)),
            "operations": self._query(f"SELECT * FROM operations WHERE project_id IN ({placeholders}) ORDER BY due_date", tuple(ids)),
        }

    def material_status(self, project_id: str | None = None, issues_only: bool = False) -> list[dict[str, Any]]:
        clauses, params = [], []
        if project_id:
            clauses.append("project_id = ?")
            params.append(project_id)
        if issues_only:
            clauses.append("stock_status != '정상'")
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        return self._query("SELECT * FROM materials" + where + " ORDER BY material_lot", tuple(params))

    def inspection_issues(self, project_id: str | None = None) -> list[dict[str, Any]]:
        sql = """SELECT i.*, m.project_id, m.material_code, m.supplier, m.barcode
                 FROM incoming_inspections i JOIN materials m ON m.material_lot=i.material_lot
                 WHERE i.result != '합격'"""
        params: tuple[Any, ...] = ()
        if project_id:
            sql += " AND m.project_id = ?"
            params = (project_id,)
        return self._query(sql + " ORDER BY i.inspection_date DESC", params)

    def quote_analysis(self, project_id: str | None = None, equipment_type: str | None = None) -> list[dict[str, Any]]:
        sql = """SELECT p.project_id,p.customer,p.industry,p.equipment_type,p.order_amount_mkr,
                        q.predicted_cost_mkr,q.predicted_lead_days,q.margin_pct,q.risk_score,
                        q.similar_project,q.model_status
                 FROM projects p JOIN quote_predictions q ON q.project_id=p.project_id WHERE 1=1"""
        params: list[Any] = []
        if project_id:
            sql += " AND p.project_id=?"
            params.append(project_id)
        if equipment_type:
            sql += " AND p.equipment_type=?"
            params.append(equipment_type)
        return self._query(sql + " ORDER BY q.risk_score DESC", tuple(params))

    def procurement_risks(self, project_id: str | None = None, supplier: str | None = None) -> list[dict[str, Any]]:
        sql, params = "SELECT * FROM purchase_orders WHERE risk != '낮음'", []
        if project_id:
            sql += " AND project_id=?"
            params.append(project_id)
        if supplier:
            sql += " AND supplier=?"
            params.append(supplier)
        return self._query(sql + " ORDER BY delay_days DESC", tuple(params))

    def fat_quality(self, project_id: str | None = None) -> list[dict[str, Any]]:
        return self._query("SELECT * FROM fat_tests" + (" WHERE project_id=?" if project_id else "") + " ORDER BY test_id", (project_id,) if project_id else ())

    def lead_time_status(self, project_id: str | None = None) -> list[dict[str, Any]]:
        sql = """SELECT p.project_id,p.customer,p.equipment_type,p.due_date,p.status,p.progress_pct,
                        SUM(o.plan_hours) plan_hours,SUM(o.actual_hours) actual_hours,
                        SUM(CASE WHEN o.status LIKE '%지연%' THEN 1 ELSE 0 END) delayed_operations
                 FROM projects p LEFT JOIN operations o ON o.project_id=p.project_id"""
        params: tuple[Any, ...] = ()
        if project_id:
            sql += " WHERE p.project_id=?"
            params = (project_id,)
        sql += " GROUP BY p.project_id ORDER BY p.due_date"
        return self._query(sql, params)

    def equipment_alerts(self) -> list[dict[str, Any]]:
        return self._query("SELECT * FROM equipment_readings WHERE status != '정상' ORDER BY measured_at DESC")

    def claim_trace(self, claim_id: str) -> dict[str, Any]:
        claims = self._query("SELECT * FROM claims WHERE claim_id=?", (claim_id,))
        if not claims:
            return {"claim": None, "message": "클레임을 찾지 못했습니다."}
        project_id = claims[0]["project_id"]
        return {"claim": claims[0], "project": self.projects(project_id), "fat": self.fat_quality(project_id)}


class _PostgresRow(dict):
    """Dictionary row with SQLite-compatible integer indexing for shared code."""

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, int):
            return tuple(self.values())[key]
        return super().__getitem__(key)


class _PostgresCursor:
    def __init__(self, cursor: Any) -> None:
        self.cursor = cursor

    def _row(self, row: Any) -> _PostgresRow | None:
        if row is None:
            return None
        names = [column.name for column in self.cursor.description or ()]
        return _PostgresRow(zip(names, row))

    def fetchone(self) -> _PostgresRow | None:
        return self._row(self.cursor.fetchone())

    def fetchall(self) -> list[_PostgresRow]:
        return [self._row(row) for row in self.cursor.fetchall()]

    def __iter__(self):
        return iter(self.fetchall())


class _PostgresConnection:
    """Small adapter so repository query methods stay backend-independent."""

    def __init__(self, connection: Any) -> None:
        self.connection = connection

    @staticmethod
    def _sql(sql: str) -> str:
        return sql.replace("?", "%s").replace("INSERT OR IGNORE INTO", "INSERT INTO")

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> _PostgresCursor:
        if "INSERT OR IGNORE INTO" in sql:
            sql = self._sql(sql) + " ON CONFLICT DO NOTHING"
        cursor = self.connection.execute(self._sql(sql), params)
        return _PostgresCursor(cursor)

    def executemany(self, sql: str, params: list[tuple[Any, ...]]) -> None:
        with self.connection.cursor() as cursor:
            cursor.executemany(self._sql(sql), params)

    def executescript(self, script: str) -> None:
        for statement in script.split(";"):
            if statement.strip():
                self.execute(statement)

    def __enter__(self) -> "_PostgresConnection":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        if exc_type:
            self.connection.rollback()
        else:
            self.connection.commit()
        self.connection.close()


class PostgresRepository(KyungdongRepository):
    """PostgreSQL + pgvector Data Hub used when DATABASE_URL is configured."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self.db_path = None
        self._initialize()

    def _connect(self, *, register_vector_type: bool = True) -> _PostgresConnection:
        try:
            import psycopg
            from pgvector.psycopg import register_vector
        except ImportError as exc:
            raise RuntimeError("PostgreSQL 사용에는 psycopg[binary] 설치가 필요합니다.") from exc
        raw = psycopg.connect(self.database_url)
        try:
            if register_vector_type:
                register_vector(raw)
        except Exception:
            raw.close()
            raise
        return _PostgresConnection(raw)

    def _initialize(self) -> None:
        # A fresh database has no vector type until this transaction commits.
        with self._connect(register_vector_type=False) as connection:
            connection.execute("CREATE EXTENSION IF NOT EXISTS vector")
        super()._initialize()
        with self._connect() as connection:
            connection.execute("ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS embedding vector(1536)")
            connection.execute("ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS embedding_model TEXT")
            connection.execute("CREATE INDEX IF NOT EXISTS knowledge_documents_embedding_idx ON knowledge_documents USING hnsw (embedding vector_cosine_ops)")

    def table_inventory(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            return [
                {"table": name, "label": label,
                 "exists": bool(connection.execute(
                     "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=?", (name,)
                 ).fetchone()),
                 "count": connection.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
                 if connection.execute(
                     "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=?", (name,)
                 ).fetchone() else 0}
                for name, label in self.TABLE_LABELS.items()
            ]

    def table_records(self, table: str, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        if table not in self.TABLE_LABELS:
            raise ValueError("조회할 수 없는 테이블입니다.")
        if not 1 <= limit <= 100 or offset < 0:
            raise ValueError("조회 범위가 올바르지 않습니다.")
        with self._connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=?", (table,)
            ).fetchone()
            if not exists:
                return []
            columns = connection.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=? ORDER BY ordinal_position",
                (table,),
            ).fetchall()
            order = ", ".join('"' + row[0].replace('"', '""') + '"' for row in columns)
            return [dict(row) for row in connection.execute(
                f'SELECT * FROM "{table}" ORDER BY {order} LIMIT ? OFFSET ?', (limit, offset)
            ).fetchall()]

    def save_setting(self, key: str, value: str) -> None:
        with self._connect() as connection:
            connection.execute("INSERT INTO app_settings (key, value) VALUES (?, ?) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value", (key, value))

    def save_uploaded_document(self, file_id: str, filename: str, content: str | None, embedding: list[float] | None = None, embedding_model: str | None = None) -> None:
        with self._connect() as connection:
            connection.execute("""INSERT INTO knowledge_documents (document_id, filename, content, source, status, embedding, embedding_model)
                VALUES (?, ?, ?, '업로드 문서', '인덱싱 완료', ?, ?)
                ON CONFLICT (document_id) DO UPDATE SET filename=EXCLUDED.filename, content=EXCLUDED.content,
                status=EXCLUDED.status, embedding=EXCLUDED.embedding, embedding_model=EXCLUDED.embedding_model""",
                (file_id, filename, content, embedding, embedding_model))

    def insert_rows(self, table: str, rows: list[dict[str, Any]]) -> int:
        if table not in self.TABLE_LABELS or table == "knowledge_documents":
            raise ValueError("마이그레이션할 수 없는 테이블입니다.")
        if not rows:
            return 0
        columns = list(rows[0])
        names = ", ".join(f'"{column}"' for column in columns)
        placeholders = ", ".join("%s" for _ in columns)
        sql = f'INSERT INTO "{table}" ({names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING'
        with self._connect() as connection:
            connection.executemany(sql, [tuple(row[column] for column in columns) for row in rows])
        return len(rows)

    def insert_knowledge_rows(self, rows: list[dict[str, Any]]) -> int:
        """Insert migrated documents while preserving IDs and optional vectors."""
        if not rows:
            return 0
        sql = """INSERT INTO knowledge_documents
            (document_id, filename, content, source, status, embedding, embedding_model)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (document_id) DO UPDATE SET filename=EXCLUDED.filename,
              content=EXCLUDED.content, source=EXCLUDED.source, status=EXCLUDED.status,
              embedding=COALESCE(EXCLUDED.embedding, knowledge_documents.embedding),
              embedding_model=COALESCE(EXCLUDED.embedding_model, knowledge_documents.embedding_model)"""
        with self._connect() as connection:
            connection.executemany(sql, [(
                row.get("document_id"), row.get("filename"), row.get("content"),
                row.get("source"), row.get("status"), row.get("embedding"), row.get("embedding_model"),
            ) for row in rows])
        return len(rows)

    def reset_data_for_migration(self) -> None:
        """Clear demo/previous rows before a full SQLite replacement import."""
        tables = [*self.TABLE_LABELS.keys(), "knowledge_documents", "app_settings"]
        with self._connect() as connection:
            connection.execute("TRUNCATE TABLE " + ", ".join(f'\"{table}\"' for table in tables) + " CASCADE")

    def vector_search_knowledge(self, embedding: list[float], limit: int = 5) -> list[dict[str, Any]]:
        """Nearest-neighbor retrieval for callers that provide a 1536-d embedding."""
        if not 1 <= limit <= 50:
            raise ValueError("조회 범위가 올바르지 않습니다.")
        with self._connect() as connection:
            return [dict(row) for row in connection.execute("""
                SELECT document_id, filename, content, source, status,
                       embedding <=> ?::vector AS distance
                FROM knowledge_documents
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> ?::vector
                LIMIT ?
            """, (embedding, embedding, limit)).fetchall()]


def create_repository(sqlite_path: str | Path) -> KyungdongRepository:
    """Use PostgreSQL in configured environments and retain SQLite for offline tests."""
    database_url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")
    return PostgresRepository(database_url) if database_url else KyungdongRepository(sqlite_path)
