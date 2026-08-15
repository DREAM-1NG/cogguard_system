import hashlib, json
from datetime import datetime
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.case_workbench import *
from app.schemas.case_workbench import CaseLifecycle

STAGES=["semantic_enrichment","coordination_discover","propagation_analysis","student","teacher"]
def _id(prefix): return f"{prefix}_{uuid4().hex}"
def _actor(actor): return int(getattr(actor,"id",0) or 0)
def _json(v): return json.dumps(v, ensure_ascii=False, sort_keys=True, default=str)
def _required_text(value, field):
    text=str(value or "").strip()
    if not text: raise ValueError(field)
    return text
class CaseWorkbenchService:
    def __init__(self, db: AsyncSession): self.db=db
    async def create_case(self,event_id,title,actor):
        existing=(await self.db.execute(select(CaseRecord).where(CaseRecord.event_id==event_id))).scalar_one_or_none()
        if existing: return existing
        row=CaseRecord(case_id=_id("case"),event_id=event_id,title=title,created_by=_actor(actor)); self.db.add(row); await self.db.flush(); return row
    async def list_cases(self): return list((await self.db.execute(select(CaseRecord).order_by(CaseRecord.created_at.desc()))).scalars())
    async def get_case(self,case_id):
        row=(await self.db.execute(select(CaseRecord).where(CaseRecord.case_id==case_id))).scalar_one_or_none()
        if not row: raise KeyError("case not found")
        return row
    async def register_authority_source(self,name,url,actor):
        row=AuthoritySource(source_id=_id("source"),name=name,url=url); self.db.add(row); await self.db.flush(); return row
    async def list_authority_sources(self): return list((await self.db.execute(select(AuthoritySource))).scalars())
    async def review_authority_source(self,source_id,decision,tier=None,actor=None):
        row=(await self.db.execute(select(AuthoritySource).where(AuthoritySource.source_id==source_id))).scalar_one_or_none()
        if not row: raise KeyError("authority source not found")
        if decision == "allowlist":
            if tier not in {x.value for x in __import__('app.schemas.case_workbench',fromlist=['AuthorityTier']).AuthorityTier}: raise ValueError("invalid authority tier")
            row.review_status="allowlisted"; row.tier=tier
        elif decision == "reject": row.review_status="rejected"; row.tier=None
        else: raise ValueError("invalid review decision")
        row.reviewed_by=_actor(actor); await self.db.flush(); return row
    async def bind_authority_source_account(self,source_id,platform,author_id,display_name_snapshot,verification_snapshot=None,actor=None):
        source=(await self.db.execute(select(AuthoritySource).where(AuthoritySource.source_id==source_id))).scalar_one_or_none()
        if not source: raise KeyError("authority source not found")
        if source.review_status != "allowlisted": raise ValueError("allowlisted authority source required")
        platform=_required_text(platform,"platform"); author_id=_required_text(author_id,"author_id"); display_name_snapshot=_required_text(display_name_snapshot,"display_name_snapshot")
        existing=(await self.db.execute(select(AuthoritySourceAccount).where(AuthoritySourceAccount.source_id==source_id,AuthoritySourceAccount.platform==platform,AuthoritySourceAccount.author_id==author_id))).scalar_one_or_none()
        if existing: raise ValueError("authority source account already bound")
        row=AuthoritySourceAccount(source_id=source_id,platform=platform,author_id=author_id,display_name_snapshot=display_name_snapshot,verification_snapshot=_json(verification_snapshot or {}),reviewed_by=_actor(actor)); self.db.add(row); await self.db.flush(); return row
    async def list_authority_source_accounts(self,source_id):
        source=(await self.db.execute(select(AuthoritySource).where(AuthoritySource.source_id==source_id))).scalar_one_or_none()
        if not source: raise KeyError("authority source not found")
        return list((await self.db.execute(select(AuthoritySourceAccount).where(AuthoritySourceAccount.source_id==source_id).order_by(AuthoritySourceAccount.platform,AuthoritySourceAccount.author_id))).scalars())
    async def add_claim(self,case_id,authority_source_id,exact_quote,quote_start,quote_end,source_url,account,published_at,role,actor):
        # Claims currently receive the captured quotation itself (without a
        # separate full-page text payload), so its span must anchor that
        # captured source fragment exactly from offset zero.
        if quote_start != 0 or quote_end - quote_start != len(exact_quote):
            raise ValueError("exact quote span")
        source_url=_required_text(source_url,"source_url")
        source=(await self.db.execute(select(AuthoritySource).where(AuthoritySource.source_id==authority_source_id))).scalar_one_or_none()
        if not source: raise KeyError("authority source not found")
        if role == "primary" and source.review_status != "allowlisted": raise ValueError("allowlisted")
        row=CaseClaim(claim_id=_id("claim"),case_id=case_id,authority_source_id=authority_source_id,exact_quote=exact_quote,quote_start=quote_start,quote_end=quote_end,source_url=source_url,account=account,published_at=published_at,role=role,source_tier_snapshot=source.tier,source_review_snapshot=source.review_status,content_sha256=hashlib.sha256(exact_quote.encode()).hexdigest()); self.db.add(row); await self.db.flush(); return row
    async def request_run(self,case_id,snapshot_or_run_id,actor):
        await self.get_case(case_id)
        primary=(await self.db.execute(select(CaseClaim).where(CaseClaim.case_id==case_id,CaseClaim.role=="primary"))).scalars().first()
        blockers=[] if primary else ["blocked_missing_primary_claim"]
        row=CaseAnalysisLink(link_id=_id("run"),case_id=case_id,snapshot_or_run_id=snapshot_or_run_id,stages_json=_json(STAGES),blockers_json=_json(blockers)); self.db.add(row); await self.db.flush(); return _RunView(row)
    async def set_canonical_verdict(self,case_id,verdict,approved,actor):
        row=await self.get_case(case_id); row.canonical_verdict_json=_json(verdict); row.canonical_approved=approved; await self.db.flush(); return row
    async def add_action(self,case_id,description,required,actor):
        await self.get_case(case_id); row=CaseAction(action_id=_id("action"),case_id=case_id,description=description,required=required); self.db.add(row); await self.db.flush(); return row
    async def update_action(self,action_id,state,waiver_reason=None,actor=None):
        row=(await self.db.execute(select(CaseAction).where(CaseAction.action_id==action_id))).scalar_one_or_none()
        if not row: raise KeyError("action not found")
        if state=="waived" and not waiver_reason: raise ValueError("waiver reason")
        row.state=state; row.waiver_reason=waiver_reason or ""; await self.db.flush(); return row
    async def create_report(self,case_id,actor):
        case=await self.get_case(case_id); manifest={"case_id":case.case_id,"event_id":case.event_id,"title":case.title,"verdict":json.loads(case.canonical_verdict_json)}; raw=_json(manifest); html=f"<html><head><style>@media print{{body{{font-family:sans-serif}}}}</style></head><body><h1>{case.title}</h1><pre>{raw}</pre></body></html>"; row=CaseReportVersion(report_id=_id("report"),case_id=case_id,version=1,manifest_json=raw,html=html,manifest_sha256=hashlib.sha256(raw.encode()).hexdigest()); self.db.add(row); await self.db.flush(); return row
    async def close_case(self,case_id,closure_note,actor):
        case=await self.get_case(case_id)
        if not case.canonical_approved: raise ValueError("approved canonical verdict")
        actions=list((await self.db.execute(select(CaseAction).where(CaseAction.case_id==case_id,CaseAction.required==True))).scalars())
        if any(a.state not in {"completed","waived"} for a in actions): raise ValueError("required actions")
        if not closure_note.strip(): raise ValueError("closure note")
        report=await self.create_report(case_id,actor); case.lifecycle=CaseLifecycle.CLOSED.value; case.closure_note=closure_note; case.closure_report_id=report.report_id; self.db.add(CaseAuditEvent(case_id=case_id,event_type="closed",payload_json=_json({"report_id":report.report_id}))); await self.db.flush(); return case
class _RunView:
    def __init__(self,row): self.link_id=row.link_id; self.snapshot_or_run_id=row.snapshot_or_run_id; self.stages=json.loads(row.stages_json); self.blockers=json.loads(row.blockers_json)
