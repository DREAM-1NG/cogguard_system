from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import _resolve_user_from_token
from app.db.mysql import async_session_factory
from app.models.user import User
from app.schemas.case_workbench import ActionCreate, ActionUpdate, CaseCreate, ClaimCreate, CloseRequest, RunRequest, VerdictRequest
from app.services.case_workbench_service import CaseWorkbenchService
from app.utils.response import success

router=APIRouter()
_case_bearer = HTTPBearer(auto_error=False)

async def _case_user(credentials: HTTPAuthorizationCredentials | None = Depends(_case_bearer)):
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    from app.db.mysql import async_session_factory
    async with async_session_factory() as db:
        return await _resolve_user_from_token(credentials.credentials, db)

require_case_reader = _case_user

async def require_case_editor(current_user=Depends(_case_user)):
    if str(getattr(current_user, "role", "") or "") not in {"admin", "analyst"}:
        raise HTTPException(status_code=403, detail="Case operation requires analyst or admin role")
    return current_user
async def get_case_workbench_service(request: Request):
    # FastAPI resolves sibling dependencies independently. Guard this service
    # dependency before opening MySQL so unauthenticated reads consistently
    # return 401 even when the database driver is unavailable.
    if not request.headers.get("authorization"):
        raise HTTPException(status_code=401, detail="Not authenticated")
    async with async_session_factory() as db:
        yield CaseWorkbenchService(db)
def _dump(value):
    if hasattr(value,"model_dump"): return value.model_dump(mode="json")
    data={key:value for key,value in vars(value).items() if not key.startswith("_")}
    for key,value in list(data.items()): data[key]=getattr(value,"value",value)
    return data
async def _write(operation, service):
    try:
        result=await operation(); commit=service.db.commit();
        if hasattr(commit,"__await__"): await commit
    except KeyError as exc: raise HTTPException(404, str(exc)) from exc
    except ValueError as exc: raise HTTPException(400, str(exc)) from exc
    return success(data=_dump(result))
@router.post("")
async def create_case(body:CaseCreate, service:CaseWorkbenchService=Depends(get_case_workbench_service), current_user:User=Depends(require_case_editor)): return await _write(lambda:service.create_case(**body.model_dump(),actor=current_user),service)
@router.get("")
async def list_cases(service:CaseWorkbenchService=Depends(get_case_workbench_service), _current_user:User=Depends(require_case_reader)): return success(data=[_dump(row) for row in await service.list_cases()])
@router.get("/{case_id}")
async def get_case(case_id:str, service:CaseWorkbenchService=Depends(get_case_workbench_service), _current_user:User=Depends(require_case_reader)): return await _write(lambda:service.get_case(case_id),service)
@router.post("/{case_id}/claims")
async def add_claim(case_id:str, body:ClaimCreate, service:CaseWorkbenchService=Depends(get_case_workbench_service), current_user:User=Depends(require_case_editor)): return await _write(lambda:service.add_claim(case_id,**body.model_dump(),actor=current_user),service)
@router.post("/{case_id}/runs")
async def request_run(case_id:str, body:RunRequest, service:CaseWorkbenchService=Depends(get_case_workbench_service), current_user:User=Depends(require_case_editor)): return await _write(lambda:service.request_run(case_id,**body.model_dump(),actor=current_user),service)
@router.put("/{case_id}/canonical-verdict")
async def set_verdict(case_id:str, body:VerdictRequest, service:CaseWorkbenchService=Depends(get_case_workbench_service), current_user:User=Depends(require_case_editor)): return await _write(lambda:service.set_canonical_verdict(case_id,**body.model_dump(),actor=current_user),service)
@router.post("/{case_id}/actions")
async def add_action(case_id:str, body:ActionCreate, service:CaseWorkbenchService=Depends(get_case_workbench_service), current_user:User=Depends(require_case_editor)): return await _write(lambda:service.add_action(case_id,**body.model_dump(),actor=current_user),service)
@router.patch("/{case_id}/actions/{action_id}")
async def update_action(case_id:str, action_id:str, body:ActionUpdate, service:CaseWorkbenchService=Depends(get_case_workbench_service), current_user:User=Depends(require_case_editor)): return await _write(lambda:service.update_action(action_id,**body.model_dump(),actor=current_user),service)
@router.post("/{case_id}/reports")
async def create_report(case_id:str, service:CaseWorkbenchService=Depends(get_case_workbench_service), current_user:User=Depends(require_case_editor)): return await _write(lambda:service.create_report(case_id,current_user),service)
@router.post("/{case_id}/close")
async def close_case(case_id:str, body:CloseRequest, service:CaseWorkbenchService=Depends(get_case_workbench_service), current_user:User=Depends(require_case_editor)): return await _write(lambda:service.close_case(case_id,body.closure_note,current_user),service)
