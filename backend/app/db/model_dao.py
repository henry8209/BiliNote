import json
from typing import Any, Dict, Optional

from app.db.engine import get_db
from app.db.models.models import Model
from app.db.models.providers import Provider


def _parse_config(raw: Optional[str]) -> Dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _serialize_model(model: Model) -> Dict[str, Any]:
    return {
        "id": model.id,
        "provider_id": model.provider_id,
        "model_name": model.model_name,
        "created_at": model.created_at,
        "config": _parse_config(getattr(model, "config", None)),
    }


def get_model_by_id(model_id: int):
    db = next(get_db())
    try:
        model = db.query(Model).filter_by(id=model_id).first()
        return _serialize_model(model) if model else None
    finally:
        db.close()


def get_model_by_provider_and_name(provider_id, model_name: str):
    db = next(get_db())
    try:
        model = db.query(Model).filter_by(provider_id=provider_id, model_name=model_name).first()
        if model:
            return _serialize_model(model)
        return None
    finally:
        db.close()


def insert_model(provider_id, model_name: str, config: Optional[Dict[str, Any]] = None):
    db = next(get_db())
    try:
        model = Model(
            provider_id=provider_id,
            model_name=model_name,
            config=json.dumps(config, ensure_ascii=False) if config else None,
        )
        db.add(model)
        db.commit()
        db.refresh(model)
        return _serialize_model(model)
    finally:
        db.close()


def update_model_config(model_id: int, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    db = next(get_db())
    try:
        model = db.query(Model).filter_by(id=model_id).first()
        if not model:
            return None
        existing = _parse_config(getattr(model, "config", None))
        existing.update(config or {})
        model.config = json.dumps(existing, ensure_ascii=False)
        db.commit()
        db.refresh(model)
        return _serialize_model(model)
    finally:
        db.close()


def get_models_by_provider(provider_id):
    db = next(get_db())
    try:
        models = db.query(Model).filter_by(provider_id=provider_id).all()
        return [_serialize_model(m) for m in models]
    finally:
        db.close()


def delete_model(model_id: int):
    db = next(get_db())
    try:
        model = db.query(Model).filter_by(id=model_id).first()
        if model:
            db.delete(model)
            db.commit()
    finally:
        db.close()


def get_all_models():
    db = next(get_db())
    try:
        models = (
            db.query(Model)
            .join(Provider, Model.provider_id == Provider.id)
            .filter(Provider.enabled == 1)
            .all()
        )
        return [_serialize_model(m) for m in models]
    finally:
        db.close()


def ensure_models_config_column():
    """Best-effort SQLite migration for older DBs missing models.config."""
    db = next(get_db())
    try:
        bind = db.get_bind()
        if bind is None or bind.dialect.name != "sqlite":
            return
        rows = db.execute(__import__("sqlalchemy").text("PRAGMA table_info(models)")).fetchall()
        cols = {r[1] for r in rows}
        if "config" not in cols:
            db.execute(__import__("sqlalchemy").text("ALTER TABLE models ADD COLUMN config TEXT"))
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
