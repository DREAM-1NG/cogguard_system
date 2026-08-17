from __future__ import annotations

from app.core.review.evidence_contracts import EvidenceBundle, PolicyBundle, RationaleCapsule
from app.core.review.evidence_contracts import apply_claim_assessment, initialize_claim_evidence_bundle
from app.core.review.evidence_contracts import rationale_quality_gate
from app.core.review.rag import EvidenceRAG, LocalHashRag, PolicyRAG, RagDocument, ReasonBank
from app.core.review.review_context import scope_agent_context


def test_evidence_bundle_is_claim_gated_and_serializable():
    empty = EvidenceBundle.from_mapping({})
    assert empty.claim_eligible is False
    assert empty.claim_assessment == "not_assessed"
    assert empty.relation == "not_applicable"

    bundle = EvidenceBundle.from_mapping(
        {
            "claim": "A claim",
            "claim_assessment": "checkable",
            "retrieval_status": "completed",
            "source_refs": [{"doc_id": "s1", "source": "official", "source_origin": "external_provider"}],
            "quoted_spans": ["The source contradicts the claim."],
            "relation": "supported",
        }
    )
    assert bundle.claim_eligible is True
    assert bundle.relation_valid is True
    assert bundle.to_dict()["source_refs"] == ({"doc_id": "s1", "source": "official", "source_origin": "external_provider"},)


def test_policy_rag_filters_inactive_documents():
    retriever = LocalHashRag(
        [
            RagDocument("active", "policy", "Active", "harmful attack", effective=True),
            RagDocument("inactive", "policy", "Inactive", "harmful attack", effective=False),
        ]
    )
    bundles = PolicyRAG(retriever, policy_version="policy-v1").retrieve_policy("harmful attack", top_k=5)
    assert [bundle.clause_id for bundle in bundles] == ["active"]
    assert all(isinstance(bundle, PolicyBundle) and bundle.usable for bundle in bundles)


def test_evidence_rag_skips_missing_claim_and_reason_bank_is_not_evidence():
    retriever = LocalHashRag([RagDocument("s1", "source", "Title", "claim evidence")])
    skipped = EvidenceRAG(retriever).retrieve_evidence("")
    assert skipped.claim_assessment == "not_assessed"
    assert skipped.retrieval_status == "skipped_non_eligible_claim"
    assert skipped.relation == "not_applicable"

    unavailable = EvidenceRAG().retrieve_evidence("A factual claim", claim_assessment="checkable")
    assert unavailable.retrieval_status == "provider_unavailable"
    assert unavailable.relation == "not_applicable"

    no_match = EvidenceRAG(retriever).retrieve_evidence("unrelated vocabulary", claim_assessment="checkable")
    assert no_match.retrieval_status == "completed_no_relevant_evidence"
    assert no_match.relation == "not_applicable"
    assert ReasonBank(retriever).retrieve("claim")[0]["retrieval_kind"] == "rationale_example"


def test_only_an_explicit_structured_claim_becomes_query_eligible():
    not_assessed = initialize_claim_evidence_bundle(
        {"selected_posts": [{"post_id": "p1", "content": "A sentence that might contain a claim."}]}
    )
    assert not_assessed.claim_assessment == "not_assessed"
    assert not_assessed.claim_eligible is False

    checkable = initialize_claim_evidence_bundle(
        {"selected_posts": [{"post_id": "p1", "primary_claim": {"claim_text": "A checkable fact."}}]}
    )
    assert checkable.claim_assessment == "checkable"
    assert checkable.claim == "A checkable fact."


def test_insufficient_requires_completed_traceable_claim_evidence():
    initial = EvidenceBundle(
        claim="A checkable fact.",
        claim_assessment="checkable",
        retrieval_status="completed",
        source_refs=({"doc_id": "source-1", "source": "official", "source_origin": "external_provider"},),
        quoted_spans=("Quoted source text.",),
    )
    assessed = apply_claim_assessment(
        initial,
        {
            "claim_assessment": "checkable",
            "claim": "A checkable fact.",
            "assessment_reason": "externally verifiable assertion",
            "relation": "insufficient",
            "source_ref_ids": ["source-1"],
            "quoted_spans": ["Quoted source text."],
        },
    )
    assert assessed.relation == "insufficient"
    assert assessed.relation_valid is True

    noncheckable = apply_claim_assessment(
        initial,
        {
            "claim_assessment": "no_verifiable_claim",
            "claim": "",
            "assessment_reason": "opinion",
            "relation": "not_applicable",
            "source_ref_ids": [],
            "quoted_spans": [],
        },
    )
    assert noncheckable.retrieval_status == "skipped_non_eligible_claim"
    assert noncheckable.relation == "not_applicable"


def test_rationale_quality_gate_requires_task_specific_provenance():
    capsule = RationaleCapsule(
        task="claim_deception",
        capsule_text="The cited source contradicts the claim.",
        citation_coverage=1.0,
        source_traceability=True,
        relation_validity=True,
        capsule_quality_gate=True,
    )
    eligible, blockers = rationale_quality_gate(capsule, requires_evidence=True)
    assert eligible is True
    assert blockers == []


def test_review_agent_contexts_are_role_scoped():
    context = {
        "schema_version": "review-agent-input-bundle-v1",
        "input_refs": {"case_id": "case-1"},
        "review_task": "interpersonal_harm",
        "selected_posts": [
            {
                "post_id": "post-1",
                "content": "harm text",
                "claims": ["claim text"],
                "media_urls": ["image.jpg"],
                "raw_data": {"base64": "secret"},
                "harmfulness": {"score": 0.9},
            }
        ],
        "media_inputs": [{"data_url": "data:image/png;base64,secret"}],
        "active_retrieval": {"source_refs": ["source-1"]},
    }

    harm = scope_agent_context("PostHarmAgent", context)
    claim = scope_agent_context("ClaimEvidenceAgent", context)

    assert "claims" not in harm["selected_posts"][0]
    assert "media_urls" not in harm["selected_posts"][0]
    assert harm["selected_posts"][0]["harmfulness"] == {"score": 0.9}
    assert claim["selected_posts"][0]["claims"] == ["claim text"]
    assert "media_inputs" not in claim
