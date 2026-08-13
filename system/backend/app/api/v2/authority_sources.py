from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import get_current_user, require_roles
from app.db.mysql import get_db
from app.models.user import User
from app.schemas.case_workbench import AuthorityReview, AuthoritySourceCreate
from app.services.case_workbench_service import CaseWorkbenchService
from app.utils.response import success

router=APIRouter(); require_authority_reader=get_current_user; require_authority_editor=require_roles("admin","analyst"); require_authority_admin=require_roles("admin")
def get_case_workbench_service(db:AsyncSession=Depends(get_db)): return CaseWorkbenchService(db)
def _dump(row): return {key:getattr(value,"value",value) for key,value in vars(row).items() if not key.startswith("_")}
async def _write(operation, service):
    try:
        result=await operation(); commit=service.db.commit()
        if hasattr(commit,"__await__"): await commit
    except KeyError as exc: raise HTTPException(404,str(exc)) from exc
    except ValueError as exc: raise HTTPException(400,str(exc)) from exc
    return success(data=_dump(result))
@router.post("")
async def register_source(body:AuthoritySourceCreate, service:CaseWorkbenchService=Depends(get_case_workbench_service), current_user:User=Depends(require_authority_editor)): return await _write(lambda:service.register_authority_source(**body.model_dump(),actor=current_user),service)
@router.get("")
async def list_sources(service:CaseWorkbenchService=Depends(get_case_workbench_service), _current_user:User=Depends(require_authority_reader)): return success(data=[_dump(row) for row in await service.list_authority_sources()])
@router.post("/{source_id}/review")
async def review_source(source_id:str, body:AuthorityReview, service:CaseWorkbenchService=Depends(get_case_workbench_service), current_user:User=Depends(require_authority_admin)): return await _write(lambda:service.review_authority_source(source_id,**body.model_dump(),actor=current_user),service)
