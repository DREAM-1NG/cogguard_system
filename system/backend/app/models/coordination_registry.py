"""KT1 协同数据集与运行作业 ORM 模型。"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.mysql import Base


class CoordinationDataset(Base):
    """已注册的历史/上传协同数据集。"""

    __tablename__ = "coordination_datasets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="system_archive/uploaded")
    source_format: Mapped[str] = mapped_column(String(16), nullable=False, comment="csv/jsonl")
    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    has_labels: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    event_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    account_nodes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    object_ids: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    user_user_edges: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    available_relations: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    latest_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )


class CoordinationRun(Base):
    """KT1 协同检测运行作业。"""

    __tablename__ = "coordination_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="pending",
        index=True,
        comment="pending/running/completed/failed",
    )
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    run_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="rerun", comment="archive/rerun")
    discover_encoder: Mapped[str] = mapped_column(String(32), nullable=False, default="magnn")
    community_algorithm: Mapped[str] = mapped_column(String(32), nullable=False, default="leiden")
    lm_backend: Mapped[str] = mapped_column(String(32), nullable=False, default="sbert")
    gnn_backend: Mapped[str] = mapped_column(String(32), nullable=False, default="fusion_gnn")
    label_mode: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="labeled_mainline",
        comment="labeled_mainline/unlabeled_china_pretrained",
    )
    artifact_dir: Mapped[str] = mapped_column(Text, nullable=False)
    metrics_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_summary_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    pretrained_weight_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
