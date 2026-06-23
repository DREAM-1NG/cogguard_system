"""风险研判 LLM 接口预留。

当前阶段不直接发起外部 LLM 请求，只统一整理上下文、配置状态和后续接入点，
方便后续切换到真实模型而不改动上层编排逻辑。
"""

from __future__ import annotations

from app.config import settings


def _top_claims(evidence_pack: dict) -> list[str]:
    claims = evidence_pack.get("propagation", {}).get("claims", []) or []
    return [str(item.get("object_id", "")).strip() for item in claims[:3] if item.get("object_id")]


def _recommended_actions(recommendations: list[dict]) -> list[str]:
    actions: list[str] = []
    for item in recommendations[:3]:
        action = str(item.get("action", "")).strip()
        desc = str(item.get("description", "")).strip()
        if action and desc:
            actions.append(f"{action}: {desc}")
        elif action:
            actions.append(action)
    return actions


def _build_suggested_prompt(context: dict) -> str:
    claims = context.get("top_claims", []) or []
    actions = context.get("recommended_actions", []) or []
    claims_text = "；".join(claims) if claims else "暂无显著共享对象"
    actions_text = "；".join(actions) if actions else "暂无建议动作"
    return (
        "请基于以下结构化风险研判上下文，生成一段适合分析师阅读的增强摘要，并补充 3 条可执行建议：\n"
        f"- 目标话题：{context.get('target', '')}\n"
        f"- 风险等级：{context.get('risk_level', '')}\n"
        f"- 所处阶段：{context.get('phase_label', '')}\n"
        f"- 高风险信号：{'；'.join(context.get('rationale', []) or [])}\n"
        f"- 重点共享对象：{claims_text}\n"
        f"- 当前建议：{actions_text}"
    )


def build_llm_bridge_result(
    *,
    target: str,
    phase_result: dict,
    disarm_result: dict,
    evidence_pack: dict,
    recommendations: list[dict],
) -> dict:
    """返回统一的 LLM 预留接口信息。"""
    provider = (settings.RISK_LLM_PROVIDER or "").strip()
    model = (settings.RISK_LLM_MODEL or "").strip()
    base_url = (settings.RISK_LLM_BASE_URL or "").strip()
    has_key = bool((settings.RISK_LLM_API_KEY or "").strip())
    enabled = bool(provider and has_key)

    context = {
        "target": target,
        "risk_level": phase_result.get("risk_level", "low"),
        "phase": phase_result.get("phase", "seed"),
        "phase_label": phase_result.get("phase_label", "播种期"),
        "rationale": phase_result.get("rationale", []),
        "disarm_summary": disarm_result.get("summary", ""),
        "top_claims": _top_claims(evidence_pack),
        "recommended_actions": _recommended_actions(recommendations),
    }

    return {
        "provider": provider or "unconfigured",
        "model": model,
        "base_url": base_url,
        "enabled": enabled,
        "status": "ready" if enabled else "disabled",
        "reason": (
            "已检测到 LLM 配置，可在此接口上接入真实模型调用。"
            if enabled
            else "未配置 RISK_LLM_PROVIDER / RISK_LLM_API_KEY，当前仅返回接口预留信息。"
        ),
        "context": context,
        "suggested_prompt": _build_suggested_prompt(context),
        "integration_status": "placeholder",
    }
