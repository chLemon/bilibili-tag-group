"""UP 主管理服务：负责创建、查询、编辑 UP 主及其标签关联。"""
from typing import Optional

from sqlalchemy.orm import Session

from app.models.creator import Creator
from app.models.tag import Tag


class CreatorService:
    """管理 UP 主与标签关联的业务逻辑。"""

    def create_creator(
        self,
        db: Session,
        name: str,
        profile_url: str,
        tag_ids: list[int],
    ) -> Creator:
        """创建新 UP 主，并可选择同时关联标签。

        参数：
            db: SQLAlchemy Session
            name: UP 主名称
            profile_url: B 站主页链接
            tag_ids: 关联的标签 ID 列表
        """
        creator = Creator(name=name, profile_url=profile_url)
        if tag_ids:
            tags = db.query(Tag).filter(Tag.id.in_(tag_ids)).all()
            creator.tags = tags
        db.add(creator)
        db.flush()
        return creator

    def list_creators(self, db: Session) -> list[Creator]:
        """返回所有 UP 主列表（按 id 升序）。"""
        return db.query(Creator).order_by(Creator.id).all()

    def get_creator(self, db: Session, creator_id: int) -> Optional[Creator]:
        """根据 id 获取单个 UP 主，不存在时返回 None。"""
        return db.get(Creator, creator_id)

    def update_creator(
        self,
        db: Session,
        creator: Creator,
        name: Optional[str],
        enabled: Optional[bool],
        tag_ids: Optional[list[int]],
    ) -> Creator:
        """更新 UP 主字段（只修改非 None 的字段）。

        tag_ids 不为 None 时，完整替换现有标签关联。
        """
        if name is not None:
            creator.name = name
        if enabled is not None:
            creator.enabled = enabled
        if tag_ids is not None:
            tags = db.query(Tag).filter(Tag.id.in_(tag_ids)).all()
            creator.tags = tags
        db.flush()
        return creator
