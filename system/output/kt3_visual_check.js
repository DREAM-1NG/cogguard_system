async (page) => {
  const mockReport = {
    report_id: 'mock-kt3-claim-stance',
    event_id: 'demo-event',
    platform: 'mock_weibo',
    assessed_at: new Date().toISOString(),
    phase: { current_phase: 'breakout', phase_confidence: 0.82, hazard_scores: {} },
    scores: {
      overall_risk_score: 72.5,
      risk_level: 'high',
      manipulation: { score: 76, belief: 0.64, plausibility: 0.82 },
      authenticity: { score: 58, belief: 0.45, plausibility: 0.67 },
      impact: { score: 81, belief: 0.7, plausibility: 0.9 },
    },
    fusion: { conflict_mass: 0.18 },
    disarm_analysis: {
      attack_path: { score: 67.8 },
      observed_techniques: [{ technique_id: 'T001', tactic: 'amplify', name: 'Narrative amplification', belief: 0.72 }],
      predicted_next: [{ technique_id: 'T002', name: 'Cross-platform seeding', probability: 0.61 }],
      countermeasures: [{ technique_id: 'T001', action: '进入人工证据复核', priority: 'high' }],
    },
    risk_factors: {
      manipulation_factors: ['claim amplification'],
      authenticity_factors: ['coordinated reposting'],
      impact_factors: ['high engagement'],
    },
    recommendations: [{ priority: 'high', action: '启动 KT3 Agent 复核', reason: '存在 claim support 与 deny 冲突证据' }],
    kt3_harmfulness: {
      global_summary: { kt3_harm_risk_level: 'medium', claim_rank: [{ claim_id: 'claim-water', linked_posts: 3, harmful_posts: 2 }] },
      audit: { semantic_posts_used: 4, missing_claim_match_ratio: 0.25 },
      capability_boundary: { modeling_note: '当前为弱 claim/stance 检测，供人工研判入口使用。' },
      user_level: { summary: { harmful_accounts: 2 }, accounts: [] },
      community_level: { summary: { harmful_communities: 1 }, communities: [] },
      review_queue: {
        summary: { review_items: 2, retrieval_tasks: 1, agent_tasks: 2, recommended_next_action: 'manual_agent_review' },
        capability_boundary: { live_llm_or_rag: false },
        review_items: [{ id: 'p1', type: 'post', priority: 'high', agent_role: 'ClaimEvidenceAgent', reason: 'claim support with harmfulness', target_id: 'p1' }],
      },
      agent_review_suggestions: {
        review_reason: 'Claim/stance conflict found in post semantics.',
        suggested_agents: [
          { agent_name: 'ClaimEvidenceAgent', reason: 'verify claim evidence' },
          { agent_name: 'HarmfulnessJudgeAgent', reason: 'judge harmfulness with uncertainty' },
        ],
        all_agents: ['PostHarmAgent', 'ClaimEvidenceAgent', 'HarmfulnessJudgeAgent'],
      },
    },
    post_semantics: {
      analysis_scope: { input_posts: 4, normalized_posts: 4, claim_candidates: 2 },
      modeling: { encoder_backend: 'lexical-fallback' },
      summary: {
        stance_distribution: { support: 2, deny: 1, uncertain: 1 },
        top_claims: [{ claim_id: 'claim-water', linked_posts: 3, harmful_posts: 2 }],
      },
      aggregation_posts: [
        {
          post_id: 'p1',
          excerpt: '网传城市饮用水已经被污染，大家赶紧转发提醒身边人。',
          primary_claim: { claim_id: 'claim-water', claim_text: '城市饮用水被污染', score: 0.83 },
          stance: { label: 'support', confidence: 0.72, abstain: false },
          harmfulness: { label: 'harmful', score: 0.76, primary_type: 'misinformation' },
        },
        {
          post_id: 'p2',
          excerpt: '不要继续传播水源污染谣言，官方检测结果显示水质正常。',
          primary_claim: { claim_id: 'claim-water', claim_text: '城市饮用水被污染', score: 0.79 },
          stance: { label: 'deny', confidence: 0.69, abstain: false },
          harmfulness: { label: 'non_harmful', score: 0.31, primary_type: null },
        },
        {
          post_id: 'p3',
          excerpt: '水质到底有没有问题？有没有可靠检测报告？',
          primary_claim: { claim_id: 'claim-water', claim_text: '城市饮用水被污染', score: 0.55 },
          stance: { label: 'query', confidence: 0.51, abstain: false },
          harmfulness: { label: 'uncertain', score: 0.49, primary_type: 'misinformation' },
        },
      ],
    },
  };
  await page.route('**/api/v1/risk/assess**', async route => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ code: 0, msg: 'ok', data: mockReport }) });
  });
  await page.route('**/api/v1/risk/reports**', async route => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ code: 0, msg: 'ok', data: { total: 0, items: [] } }) });
  });
  await page.goto('http://127.0.0.1:5173/risk');
  await page.getByRole('button', { name: '运行评估' }).click();
  await page.getByText('KT3 主张/立场证据研判').waitFor({ timeout: 8000 });
  await page.screenshot({ path: 'G:/CISCN/CogGuard/system/output/kt3-claim-stance-risk-page.png', fullPage: true });
  return {
    title: await page.getByText('KT3 主张/立场证据研判').count(),
    dangerPanel: await page.getByText('近期疑似传播/有害推文').count(),
    safePanel: await page.getByText('近期辟谣/反驳推文').count(),
    stancePanel: await page.getByText('近期推文情感/立场占比').count(),
    claimCloud: await page.getByText('近期推文高频主张').count(),
    gateText: await page.getByText('gold-control').count(),
    selectedButton: await page.getByRole('button', { name: '启动研判任务' }).count(),
  };
}
