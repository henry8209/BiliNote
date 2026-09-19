from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.model import ModelService
from app.utils.response import ResponseWrapper as R

router = APIRouter()
modelService = ModelService()


class CreateModelRequest(BaseModel):
    provider_id: str
    model_name: str
    thinking: Optional[Dict[str, Any]] = None


class ThinkingUpdateRequest(BaseModel):
    thinking: Dict[str, Any]


class ModelItem(BaseModel):
    id: int
    model_name: str


@router.get("/model_list")
def model_list():
    try:
        return R.success(modelService.get_all_models(True), msg="获取模型列表成功")
    except Exception as e:
        return R.error(e)


@router.get("/models/delete/{model_id}")
def delete_model(model_id: int):
    try:
        success = modelService.delete_model_by_id(model_id)
        if success:
            return R.success(msg="模型删除成功")
        else:
            return R.error("模型不存在或删除失败")
    except Exception as e:
        return R.error(f"删除模型失败: {e}")


@router.get("/model_list/{provider_id}")
def model_list_by_provider(provider_id):
    return R.success(modelService.get_all_models_by_id(provider_id))


@router.post("/models")
def create_model(data: CreateModelRequest):
    success = ModelService.add_new_model(
        data.provider_id, data.model_name, thinking=data.thinking
    )
    if not success:
        return R.error("模型添加失败")
    return R.success(msg="模型添加成功")


@router.get("/model_enable/{provider_id}")
def get_enabled_models_by_provider(provider_id: str):
    try:
        models = modelService.get_enabled_models_by_provider(provider_id)
        return R.success(models, msg="获取启用模型成功")
    except Exception as e:
        return R.error(f"获取启用模型失败: {e}")


@router.get("/models/thinking_profile")
def get_thinking_profile(model_name: str):
    """Suggest a thinking profile for a model name (does not write DB)."""
    try:
        profile = ModelService.suggest_thinking(model_name)
        return R.success(profile, msg="ok")
    except Exception as e:
        return R.error(str(e))


@router.post("/models/{model_id}/thinking")
def update_model_thinking(model_id: int, data: ThinkingUpdateRequest):
    try:
        updated = ModelService.update_model_thinking(model_id, data.thinking)
        if not updated:
            return R.error("模型不存在或更新失败")
        return R.success(updated, msg="推理設定已更新")
    except Exception as e:
        return R.error(str(e))
