# 鎶€鏈儗鏅€昏

> **鐢ㄩ€?*锛氭€昏涓夋潯鍏抽敭鎶€鏈殑鐮旂┒瀹氫綅銆佸綋鍓嶅伐绋嬪熀绾垮拰鎺ㄨ崘闃呰椤哄簭銆? 
> **鍙椾紬**锛氱爺绌跺疄鐜拌€呫€佺郴缁熻璁＄淮鎶よ€呫€佸悗缁墽琛?ARIS 浠诲姟鐨?agent銆? 
> **缁存姢瑙勫垯**锛氬彧鍐欑ǔ瀹氱爺绌惰儗鏅拰鎶€鏈嚎鍏ュ彛锛涘叿浣撳伐绋嬩换鍔＄姸鎬佹斁鍏?`../../engineering/development-roadmap.md`銆?
## 1. 椤圭洰涓荤嚎

鏈」鐩潰鍚戠綉缁滆垎璁哄鎶楀満鏅腑鐨勮法骞冲彴鍗忓悓鏀诲嚮銆?
绯荤粺鍥寸粫涓夊ぇ涓昏鍔熻兘褰㈡垚闂幆锛屾瘡涓姛鑳戒笅鍖呭惈澶氫釜瀛愬姛鑳斤紝鎶€鏈寜閲嶈绋嬪害鍒嗕负鍏抽敭鎶€鏈拰鍏跺畠鎶€鏈細

```
鍔熻兘涓€: 鍗忓悓鍙戠幇 鈹€鈹€鈫?鍔熻兘浜? 浼犳挱鐩戞帶 鈹€鈹€鈫?鍔熻兘涓? 鎶ュ憡鐮斿垽
                                                    鈹?        鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?```

| 鍔熻兘 | 鍏抽敭鎶€鏈?| 璇存槑 |
|------|---------|------|
| 鍗忓悓鍙戠幇 | 璺ㄥ钩鍙板叡鍚岃涓虹壒寰佸鐢ㄨ瀺鍚堟娴?| 鐢ㄥ钩鍙版棤鍏崇殑琛屼负淇″彿鍙戠幇鍗忓悓缇や綋锛涘唴瀹规娴嬩笉浣滃崗鍚屼俊鍙?|
| 浼犳挱鐩戞帶 | LLM+鏃跺簭棰勬祴锛堜簨浠惰妯￠娴嬶級 | 浜嬩欢鏉′欢浣撳埗鍒囨崲鐨勭骇鑱旇妯″墠鐬婚娴嬶紱鍊熼壌鐭ュ井浜у搧褰㈡€?|
| 鎶ュ憡鐮斿垽 | Phase-Aware Hazard + DISARM 璺緞棰勫垽锛堝 Agent 缂栨帓锛?| 闃舵棰勮 + 鏀诲嚮璺緞棰勫垽 + 鍙嶅埗锛汚gent/RAG 浣滅紪鎺掍笌鍛堢幇灞?|

鍏抽敭鎶€鏈槸浠庡姛鑳戒腑鎻愮偧鐨勬牳蹇冨垱鏂扮偣锛屼笉绛夊悓浜庡姛鑳芥湰韬€傚叾瀹冩妧鏈悗鏈熷姩鎬佽皟鏁淬€?鏂瑰悜鏇存柊瑙佸悇鎶€鏈嚎鑳屾櫙鏂囨。锛?026-06-02锛夈€?
## 2. 褰撳墠宸ョ▼鍩虹嚎

- 宸ョ▼鍩虹嚎锛歚release-0.2`
- 浜у搧浠ｇ爜鏍癸細`system/`
- 鐭湡楠岃瘉鑼冨洿锛歚weibo`銆乣douyin`銆乣xhs`銆乣news`锛沗mock_weibo` 浠呯敤浜庢祴璇?- 鍙傝€冭竟鐣岋細`MediaCrawler-main/`銆乣NewsCrawler-main/`銆乣CooRTweet-master/`

浠撳簱鍒嗗眰濡備笅锛?
- `doc/`锛氶暱鏈熸枃妗ｄ笌鎶€鏈儗鏅?- `aris/`锛氭寜鍏抽敭鎶€鏈媶鍒嗙殑鐙珛鎵ц宸ヤ綔绌洪棿
- `system/`锛氬敮涓€浜у搧浠ｇ爜涓荤嚎

## 3. 褰撳墠瀹炵幇鐘舵€?
鎸?`release-0.2` 褰撳墠浠ｇ爜鍜?`doc/engineering/development-roadmap.md` 鍙ｅ緞锛?
- 鏁版嵁閲囬泦锛氬凡瀹屾垚鍐呯疆 social/news runtime cutover锛涚郴缁熻繍琛屼笉鍐嶄緷璧?`MediaCrawler-main`銆乣NewsCrawler-main` 鎴?`CooRTweet-master`
- 缁熶竴鍒嗘瀽搴曞骇锛歚EventSnapshot` / `AnalysisRun` / V2 REST / SSE recovery / executor 宸茶疮閫氾紝Coordination Discover銆丳ropagationAnalysis銆丼tudent銆乀eacher 浣跨敤鍚屼竴 snapshot seam
- 鍗忓悓鍙戠幇锛圕oordinationDiscover锛夛細宸蹭粠鍏变韩瀵硅薄 baseline 鍗囩骇涓?evidence-first runtime锛岃鐩?URL銆佸獟浣撱€佽瘽棰樸€佸疄浣撱€佺洰鏍囥€佸師鐢熷叧绯汇€佽繎閲嶅鍐呭锛屽苟杈撳嚭 1h/6h/24h 閲嶅彔绐楀彛銆佺ぞ鍖鸿氨绯汇€侀浂妯″瀷鏄捐憲鎬у拰鎵板姩椴佹鎬?- 浼犳挱鐩戞帶锛圥ropagationAnalysis锛夛細宸插唴缃?event bundle銆乸ublic fixture loader銆乴ive fallback銆乭indcast protocol銆?0/95 split-conformal interval銆乶ext-hop ranking銆乸latform hindcast 鍜?baseline registry锛涘彲閮ㄧ讲 TGN/DyGFormer/CasFlow/CasFT checkpoint 涓庡叕寮€ benchmark 姝ｅ紡璇勬祴浠嶅緟瀹屾垚
- 鎶ュ憡鐮斿垽锛圧eview锛夛細宸叉帴閫氬悓姝?Student runtime銆佸紓姝?Teacher 5+1+1 advisory DAG銆乧anonical approval / active pointer / rollback / active learning governance helper锛涜捀棣忚缁冦€乤pproved checkpoint 鍜屽畬鏁?adjudication UI 浠嶅緟瀹屾垚
- 鐪嬫澘/棰勮/鎶ュ憡锛歚/analysis` 宸ヤ綔鍙板凡灞曠ず鍏抽敭鎶€鏈粨鏋滐紝棰勮涓績銆佹姤鍛婁腑蹇冨拰妯″瀷娌荤悊 UI 鏀惧湪鍚庣画闃舵

## 4. 宸ョ▼鍘熷垯

- 浼樺厛淇濇寔 `system/` 涓哄敮涓€浠ｇ爜涓荤嚎锛屼笉鎼姩浜у搧浠ｇ爜鏍?- 鍙傝€冨瓙浠撻粯璁ゅ彧璇伙紝涓嶅湪鏃犳槑纭换鍔℃椂淇敼
- 瑙勫垯涓庤瘉鎹紭鍏堜簬榛戠洅 LLM 瑁佸喅
- ARIS 鍙綔涓烘墽琛屽伐浣滅┖闂村拰鐮斿彂缂栨帓灞傦紝涓嶈繘鍏ヤ骇鍝佽繍琛屾椂
- 姣忔潯鍏抽敭鎶€鏈崟鐙伐浣滅┖闂淬€佸崟鐙?brief銆佸崟鐙垎鏀?
## 5. ARIS 浣跨敤鍘熷垯

鏈粨搴撲笉 vendoring 涓婃父 ARIS skill 浠ｇ爜锛屽彧淇濈暀鏈湴閫傞厤灞傦細

- `aris/shared/`锛氱粺涓€ runner銆丟PU 妯℃澘銆佷骇鐗╃瓥鐣ャ€佽瘎瀹℃竻鍗?- `aris/tech-01-coordination/`锛氬叧閿妧鏈竴鎵ц鍏ュ彛
- `aris/tech-02-propagation/`锛氬叧閿妧鏈簩鎵ц鍏ュ彛
- `aris/tech-03-risk/`锛氬叧閿妧鏈笁鎵ц鍏ュ彛

鎵ц鏃朵笉瑕佸湪浠撳簱鏍瑰垱寤哄崟涓€ `RESEARCH_BRIEF.md`銆傛瘡娆￠兘浠庣洰鏍?`aris/tech-*` 宸ヤ綔绌洪棿杩涘叆銆?
## 6. 鎺ㄨ崘闃呰椤哄簭

1. `AGENTS.md`
2. `doc/engineering/development-roadmap.md`
3. `system/README.md`
4. `aris/README.md`
5. 鐩爣 `aris/tech-*/README.md`
6. 鐩爣鎶€鏈殑鑳屾櫙鏂囨。

## 7. 鍏抽敭鍙傝€冩枃鐚叆鍙?
- [`../literature-references.md`](../literature-references.md)
- [`../../../../materials/寮€棰樻姤鍛?doc`](../../../../materials/寮€棰樻姤鍛?doc)
- [`../../engineering/development-roadmap.md`](../../engineering/development-roadmap.md)

涓夋潯鎶€鏈嚎鐨勫叿浣撹儗鏅垎鍒锛?
- [coordination-detection.md](coordination-detection.md)
- [propagation-analysis.md](propagation-analysis.md)
- [risk-disarm.md](risk-disarm.md)

