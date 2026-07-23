# CogGuard锛氶潰鍚戣法骞冲彴鍗忓悓鎿嶇旱鍒嗘瀽鐨勮瘉鎹┍鍔ㄥ師鍨嬬郴缁?
CogGuard 鏄竴涓潰鍚戠珵璧涘拰鐮旂┒楠岃瘉鐨勫紑婧愬師鍨嬶紝鐩爣鏄洿缁曡法骞冲彴鍗忓悓鎿嶇旱娲诲姩寤虹珛涓€鏉″彲瑙ｉ噴銆佸彲澶嶆牳鐨勫垎鏋愰摼璺細

`浜嬩欢 -> 璇佹嵁 -> 鍗忓悓 -> 浼犳挱 -> 椋庨櫓 -> 澶勭疆`

浠撳簱褰撳墠浠?`release-0.2` 涓哄伐绋嬪熀绾匡紝涓荤嚎浠ｇ爜浣嶄簬 [system/README.md](system/README.md) 瀵瑰簲鐨?`system/` 鐩綍銆?
Current semantic capabilities are **Coordination Discover**, **Propagation Analysis**, and **Risk Review**. Current semantic paths are `system/research/coordination_discover/`, `system/research/coordination_detect/`, `system/research/propagation_analysis/`, `system/research/review_teacher/`, and `system/runtimes/review_student/`.

## 褰撳墠鍩虹嚎

- 褰撳墠宸ョ▼鍩虹嚎锛歚release-0.2`
- 褰撳墠鍞竴浜у搧浠ｇ爜鏍癸細`system/`
- 褰撳墠鐭湡楠岃瘉鑼冨洿锛歚weibo`銆乣douyin`銆乣xhs`銆乣news`锛宍mock_weibo` 浠呯敤浜庢祴璇?- 褰撳墠鍐呯疆 runtime锛歚system/runtimes/social_runtime/`銆乣system/runtimes/news_runtime/`銆乣system/runtimes/review_student/`
- 褰撳墠鐮旂┒ runtime锛歚system/research/coordination_discover/`銆乣system/research/coordination_detect/`銆乣system/research/propagation_analysis/`銆乣system/research/review_teacher/`
- 涓婃父鍙傝€冭竟鐣岋細`MediaCrawler-main/`銆乣NewsCrawler-main/`銆乣CooRTweet-master/` 浠呬繚鐣欎綔婧簮涓庤鍙瘉褰掓。
- 绔炶禌鏉愭枡鐩綍锛歔`../materials/`](../materials/)锛圥PT銆佺敵鎶ヤ功銆佸紑棰樻潗鏂欑瓑锛屼笉鏀惧叆浜у搧浠ｇ爜鐩綍锛?- 浠撳簱绾т笂涓嬫枃鍏ュ彛锛歔`AGENTS.md`](AGENTS.md)
- ARIS 宸ヤ綔绌洪棿鍏ュ彛锛歔`aris/README.md`](aris/README.md)
- 椤圭洰缁撴瀯杈圭晫璇存槑锛歔`doc/engineering/project-map.md`](doc/engineering/project-map.md)

## 浠撳簱鍒嗗眰

| 灞?| 璺緞 | 浣滅敤 |
|------|------|------|
| 闀挎湡鏂囨。灞?| [`doc/`](doc/) | 寮€鍙戣繘搴︺€佺幆澧冭鏄庛€佹妧鏈儗鏅€佸彉鏇存棩蹇?|
| ARIS 宸ヤ綔绌洪棿灞?| [`aris/`](aris/) | 閽堝鍏抽敭鎶€鏈竴/浜?涓夌殑鐙珛 ARIS 鎵ц鍏ュ彛 |
| 浜у搧浠ｇ爜灞?| [`system/`](system/) | 褰撳墠鍞竴鏈夋晥鐨勫悗绔€佸墠绔€侀儴缃蹭笌娴嬭瘯浠ｇ爜 |
| 鍐呯疆 runtime 灞?| `system/runtimes/social_runtime/` `system/runtimes/news_runtime/` `system/runtimes/review_student/` | 褰撳墠绯荤粺瀹為檯鎵ц鐨?vendored crawler runtime 涓庡彲閮ㄧ讲 Student runtime |
| 绯荤粺鐮旂┒鍒跺搧灞?| `system/research/coordination_discover/` `system/research/coordination_detect/` `system/research/propagation_analysis/` `system/research/review_teacher/` | 绯荤粺鍙鍙栫殑 Coordination Discover/Detect銆丳ropagationAnalysis 鍗忚/benchmark 涓?Review Teacher DAG 鐮旂┒ runtime |
| 涓婃父鍙傝€冨眰 | `MediaCrawler-main/` `NewsCrawler-main/` `CooRTweet-master/` | 涓婃父鍙傝€冧笌璁稿彲璇佹函婧愶紝涓嶄綔涓虹郴缁熻繍琛屽墠鎻?|
| 澶栧眰绔炶禌鏉愭枡灞?| [`../materials/`](../materials/) | PPT銆佺敵鎶ヤ功銆佸紑棰樻潗鏂欎笌绔炶禌浜や粯鏉愭枡 |

## 褰撳墠宸ョ▼鐘舵€?
浠?[`doc/engineering/development-roadmap.md`](doc/engineering/development-roadmap.md) 涓哄噯锛屽綋鍓嶇姸鎬佸彲姒傛嫭涓猴細

| 妯″潡 | 鐘舵€?| 璇存槑 |
|------|------|------|
| 鏁版嵁閲囬泦 | MVP 宸插畬鎴?| Mock + 鐪熷疄鐖櫕灏佽宸叉帴鍏?|
| 缁熶竴鍒嗘瀽搴曞骇 | 鍏抽敭鎶€鏈鍙ｅ凡璐€?| `EventSnapshot` / `AnalysisRun` / V2 REST / SSE 鎭㈠ / execute 鍏ュ彛宸叉帴鍏ワ紱Coordination Discover銆丳ropagationAnalysis銆丼tudent銆乀eacher 鍧囩粡缁熶竴绔彛杩愯 |
| 鍗忓悓妫€娴?| Coordination Discover evidence runtime 宸叉帴鍏?| `CoordinationEngine.analyze(snapshot, options)` 榛樿杩愯 evidence-first Coordination Discover锛氬琛屼负 evidence edge銆?h/6h/24h 閲嶅彔绐楀彛銆佺ぞ鍖鸿氨绯汇€侀浂妯″瀷鏄捐憲鎬с€佹壈鍔ㄩ瞾妫掓€?|
| 浼犳挱鐩戞帶 | Propagation Analysis hindcast 鍗忚宸叉帴鍏?| `PropagationEngine.hindcast(snapshot, options)` 杈撳嚭瑙勬ā棰勬祴銆?0/95 split-conformal 鍖洪棿銆佷笅涓€璺虫帓鍚嶃€佸钩鍙?hindcast 鍜屽熀绾?registry锛汿GN/DyGFormer/CasFlow/CasFT 浠嶉渶 approved checkpoint 鎵嶈兘鎴愪负鐮旂┒涓诲紶 |
| 璐︽埛鐩戞祴 | MVP 宸插畬鎴?| 宸叉湁鐢诲儚銆佽嚜鍔ㄥ寲璇勫垎涓?BotRHG 椋庢牸绀句氦鏈哄櫒浜烘娴?API锛屽緟琛ュ巻鍙插弬涓庝笌鍓嶇娣卞害灞曠ず |
| Teacher-Student 瀹℃煡 | Review runtime seam 宸叉帴鍏?| Student 鍚屾 shadow runtime銆乀eacher 5+1+1 advisory DAG銆乧anonical 瀹℃壒/妯″瀷婵€娲?鍥炴粴/涓诲姩瀛︿範娌荤悊 helper 宸茶惤鍦帮紱钂搁璁粌涓?approved checkpoint 浠嶆槸涓嬩竴闃舵 |
| 鐪嬫澘/棰勮/鎶ュ憡 | 閮ㄥ垎瀹屾垚 | dashboard銆侀闄╅〉涓?`/analysis` 宸ヤ綔鍙板凡钀藉湴锛涘畬鏁?adjudication UI銆佹ā鍨嬬増鏈樊寮傚拰鎶ュ憡涓績浠嶅緟瀹屽杽 |

## 蹇€熷紑濮?
```bash
# 1. 鍚姩鍩虹鏈嶅姟
cd system
cp .env.example .env
docker compose up -d

# 2. 鍚姩鍚庣
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000

# 3. 鍚姩鍓嶇
cd ../frontend
npm install
npm run dev
```

- 璇︾粏鐜涓庡惎鍔ㄦ楠よ [`doc/engineering/environment-setup.md`](doc/engineering/environment-setup.md)
- 璇︾粏绯荤粺寮€鍙戣鏄庤 [`system/README.md`](system/README.md)

## ARIS 宸ヤ綔娴?
濡傛灉浠诲姟鐢?ARIS/Claude Code/Codex 椹卞姩锛屼笉鐩存帴鍦ㄤ粨搴撴牴闅忔剰寮€宸ワ紝鎸変笅闈㈣矾寰勬墽琛岋細

1. 鍏堣 [`AGENTS.md`](AGENTS.md)銆乕`doc/engineering/development-roadmap.md`](doc/engineering/development-roadmap.md)銆乕`system/README.md`](system/README.md)
2. 杩涘叆 [`aris/README.md`](aris/README.md)锛岄€夋嫨鐩爣鎶€鏈伐浣滅┖闂?3. 浠?`release-0.2` 鎷夊嚭鎶€鏈垎鏀細
   - `aris/t1-*`
   - `aris/t2-*`
   - `aris/t3-*`
4. 闃呰璇ユ妧鏈洰褰曚笅鐨?`README.md`銆乣RESEARCH_BRIEF.md`銆乣ACCEPTANCE.md`
5. 鍙湪璇ュ伐浣滅┖闂存槑纭厑璁哥殑璺緞鍐呬慨鏀逛唬鐮佷笌鏂囨。

璇存槑锛?
- 鏈粨搴撲笉 vendoring 涓婃父 ARIS skill 浠ｇ爜锛屽彧鎻愪緵鏈湴閫傞厤灞傚拰绋冲畾鏂囨。
- 涓嶄娇鐢ㄤ粨搴撴牴鍗曚竴 `RESEARCH_BRIEF.md`
- 姣忔鎵ц閮戒粠鐩爣 `aris/tech-*` 宸ヤ綔绌洪棿杩涘叆锛岄伩鍏嶄笉鍚屾妧鏈嚎浜掔浉瑕嗙洊

## 浠撳簱缁撴瀯

```text
cogguard_system/
鈹溾攢鈹€ AGENTS.md
鈹溾攢鈹€ CLAUDE.md
鈹溾攢鈹€ README.md
鈹溾攢鈹€ aris/
鈹?  鈹溾攢鈹€ README.md
鈹?  鈹溾攢鈹€ shared/
鈹?  鈹溾攢鈹€ tech-01-coordination/
鈹?  鈹溾攢鈹€ tech-02-propagation/
鈹?  鈹斺攢鈹€ tech-03-risk/
鈹溾攢鈹€ doc/
鈹?  鈹溾攢鈹€ engineering/
鈹?  鈹?  鈹溾攢鈹€ product-requirements.md
鈹?  鈹?  鈹溾攢鈹€ project-map.md
鈹?  鈹?  鈹溾攢鈹€ development-roadmap.md
鈹?  鈹?  鈹溾攢鈹€ development-log.md
鈹?  鈹?  鈹斺攢鈹€ environment-setup.md
鈹?  鈹斺攢鈹€ research/
鈹?      鈹溾攢鈹€ project-positioning-baseline.md
鈹?      鈹溾攢鈹€ literature-references.md
鈹?      鈹溾攢鈹€ time-series-forecasting-notes.md
鈹?      鈹斺攢鈹€ key-technology-background/
鈹溾攢鈹€ system/
鈹?  鈹斺攢鈹€ runtimes/
鈹?      鈹溾攢鈹€ social_runtime/
鈹?      鈹斺攢鈹€ news_runtime/
鈹溾攢鈹€ MediaCrawler-main/
鈹溾攢鈹€ NewsCrawler-main/
鈹斺攢鈹€ CooRTweet-master/
```

## 鍏抽敭鏂囨。

- [`AGENTS.md`](AGENTS.md)锛氫粨搴撶骇涓婁笅鏂囥€佺害鏉熶笌涓荤嚎鍙欎簨
- [`doc/engineering/project-map.md`](doc/engineering/project-map.md)锛氶」鐩湴鍥俱€佺洰褰曡竟鐣屼笌榛樿淇敼鑼冨洿
- [`doc/engineering/development-roadmap.md`](doc/engineering/development-roadmap.md)锛氬綋鍓嶇姸鎬佷笌浼樺厛绾?- [`doc/research/key-technology-background/overview.md`](doc/research/key-technology-background/overview.md)锛氭€绘妧鏈儗鏅?- [`aris/README.md`](aris/README.md)锛欰RIS 鍏ュ彛涓庡伐浣滄祦璇存槑
- [`system/README.md`](system/README.md)锛氫富绾夸唬鐮佽繍琛屼笌鎺ュ彛璇存槑
- [`../materials/README.md`](../materials/README.md)锛氱珵璧涙潗鏂欑洰褰曡鏄庯紙浣嶄簬浠撳簱澶栧眰锛?
## Runtime 涓庢函婧?
- 绯荤粺杩愯鏃跺彧渚濊禆 `system/runtimes/social_runtime/` 涓?`system/runtimes/news_runtime/`
- `MediaCrawler-main/`銆乣NewsCrawler-main/`銆乣CooRTweet-master/` 淇濈暀浣滀笂娓稿弬鑰冦€佽鍙瘉涓庡樊寮傛函婧?- `system/backend/app/core/coordination_baseline/` 鏄綋鍓?CooRTweet 椋庢牸鍏煎 baseline module锛屼笉浠?`CooRTweet-master` 涓烘墽琛屽墠鎻愶紱Coordination Discover 姝ｅ紡鏂规硶鍚嶄娇鐢?Coordination Discover / Coordination Detect

## Attribution

- `system/runtimes/social_runtime/` vendored 鑷?MediaCrawler 涓婃父鏍稿績锛屼繚鐣欏叾璁稿彲璇佷笌缃插悕鏂囦欢
- `system/runtimes/news_runtime/` vendored 鑷?NewsCrawler 涓婃父鏍稿績锛屼繚鐣欏叾璁稿彲璇佷笌缃插悕鏂囦欢

## Vendored Runtime License / Distribution

- `system/runtimes/social_runtime/` follows the upstream non-commercial learning/research license and must not be treated as permissive commercial code.
- `system/runtimes/news_runtime/` is distributed under GPL-3.0.
- Distributors must review combined-work obligations before redistribution and preserve all upstream attribution and license files.

## 璁稿彲璇?
鏈」鐩粎鐢ㄤ簬瀛︽湳鐮旂┒銆佹暀瀛︽紨绀哄拰绔炶禌鍘熷瀷楠岃瘉銆?
