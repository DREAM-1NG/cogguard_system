# Case Workbench Research Archive

This directory defines the append-only provenance protocol for research that
supports a Case Workbench claim. It records how sources were found and how a
reviewed source conversion is tied back to exact bytes and an exact excerpt.

## Search Records

Record every query and every returned hit in `structured-search-records.jsonl`
before selecting sources. Each hit remains in the record with a disposition of
`candidate`, `verified`, or `rejected`; rejected hits must include their
rejection reason. A verified hit must record both its source account and its
publication time.

## Reviewed Archives

Downloaded original source bytes stay outside Git in a separately controlled
source directory. After review, commit only the converted Markdown, its
`.meta.json`, and an `archive-manifest.json` entry that records both hashes,
the MarkItDown version, and the exact verified excerpt span. The verifier
checks bytes and spans; it does not execute Markdown or metadata.

A hostname or title match alone never approves an Authority Source. Approval
requires reviewed source provenance that supports the specific claim.

## Second-Platform Outcome

When a same-event Douyin or Xiaohongshu (XHS) source is verified, add a reviewed
`second_platform` entry to the manifest. When neither platform has a verified
same-event source, commit an explicit `platform-gap.json` instead:

```json
{
  "status": "unverified_second_platform",
  "summary": "No same-event Douyin or XHS source body was verified from archived pages.",
  "searches": [
    {
      "candidate_platform": "douyin",
      "query": "the recorded query",
      "provider": "the search provider",
      "searched_at": "2026-08-11T00:00:00+00:00",
      "rejected_urls": ["https://example.com/candidate"],
      "disposition_reason": "Why this candidate was not verifiable source evidence."
    },
    {
      "candidate_platform": "xhs",
      "query": "the recorded query",
      "provider": "the search provider",
      "searched_at": "2026-08-11T00:00:00+00:00",
      "rejected_urls": [],
      "disposition_reason": "Why no verifiable source body was archived."
    }
  ]
}
```

Do not fill the evidence set with unrelated platform content to make the
archive appear complete.
