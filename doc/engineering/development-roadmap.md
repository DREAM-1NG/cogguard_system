# CogGuard 璁捐鏂规涓庡紑鍙戣繘搴?
> **鐢ㄩ€?*锛氳褰曞綋鍓嶅伐绋嬬姸鎬併€佹ā鍧椾紭鍏堢骇銆佸墿浣欏紑鍙戜换鍔″拰宸查€氳繃楠岃瘉銆? 
> **鍙椾紬**锛氬紑鍙戣€呫€侀」鐩淮鎶よ€呫€佸悗缁墽琛屼换鍔＄殑 AI agent銆? 
> **缁存姢瑙勫垯**锛氬彧缁存姢鍙墽琛屽伐绋嬭矾绾垮拰鐘舵€侊紱鐮旂┒瀹氫綅銆佹枃鐚緷鎹拰鍏抽敭鎶€鏈儗鏅斁鍏?`../research/`銆?
> 鏈€鍚庢洿鏂帮細2026-07-19

## 鎶€鏈喅绛栬褰?
### 宸茬‘瀹氱殑鎶€鏈€夊瀷

| 鍐崇瓥椤?| 鏂规 | 鐞嗙敱 |
|--------|------|------|
| 鍚庣妗嗘灦 | FastAPI (Python 3.11+) | 寮傛楂樻€ц兘锛屼笌鍙傝€冮」鐩妧鏈爤涓€鑷?|
| 鍓嶇妗嗘灦 | Vue 3 + TypeScript + Vite 6 | 涓?NewsCrawler 鍓嶇涓€鑷达紝鐢熸€佹垚鐔?|
| UI 缁勪欢搴?| Ant Design Vue 4 | 涓悗鍙扮鐞嗙郴缁熺粍浠朵赴瀵岋紝閫傚悎鏁版嵁鍒嗘瀽鍦烘櫙 |
| 缁撴瀯鍖栧瓨鍌?| MySQL 8.0+ | 鐢ㄦ埛銆佷换鍔°€佸憡璀︺€佹渚嬬瓑缁撴瀯鍖栨暟鎹?|
| 闈炵粨鏋勫寲瀛樺偍 | MongoDB 7.0+ | 甯栧瓙銆佽瘎璁恒€佺埇鍙栧師濮嬫暟鎹瓑 |
| 缂撳瓨/闃熷垪 | Redis 7.0+ | 缂撳瓨銆佷細璇濈鐞嗐€丆elery 娑堟伅闃熷垪 |
| 鍥惧垎鏋?| NetworkX + igraph (鍐呭瓨) | 褰撳墠闃舵浣跨敤鍐呭瓨鍥惧垎鏋愶紝棰勭暀 Neo4j 鎵╁睍鎺ュ彛 |
| CooRTweet 闆嗘垚 | Python 閲嶅啓鏍稿績绠楁硶 | 閬垮厤 R 渚濊禆锛屼娇鐢?pandas + networkx 瀹炵幇 |
| BotRHG 绀句氦鏈哄櫒浜烘娴?| 杞婚噺绯荤粺閫傞厤鍣?| 瀵规帴 NLPCC 2026 BotRHG 鏂规硶濂戠害锛岃緭鍑哄彲闈犳€ц矾鐢便€並NN 鏀寔瓒呰竟涓庨€夋嫨鎬ф畫宸慨姝ｇ粨鏋?|
| LLM 鏀寔 | 鏆備笉闆嗘垚锛岄鐣欐帴鍙?| 褰撳墠鐢ㄨ鍒欏紩鎿?+ NLP 妯″瀷锛屽悗缁彲鎺ュ叆 LLM |
| 浠诲姟闃熷垪 | Celery + Redis | 鐖櫕銆佸垎鏋愮瓑鑰楁椂鎿嶄綔寮傛鎵ц |
| 缁熶竴鍒嗘瀽鍏ュ彛 | EventSnapshot + AnalysisRun + V2 API | Coordination Discover/Propagation Analysis/Review 鍏变韩涓嶅彲鍙樿緭鍏ャ€佺姸鎬佹満銆丷EST/SSE 鎭㈠璺緞 |
| 鍖呯鐞?| uv (鍚庣) / npm (鍓嶇) | 楂樻晥渚濊禆绠＄悊 |

---

## ARIS 浠撳簱娌荤悊涓庝笁鎶€鏈伐浣滅┖闂?
- [x] 鏂板鏍?`CLAUDE.md`銆乣aris/README.md` 涓?`doc/research/key-technology-background/`锛屾槑纭粨搴撳垎灞?- [x] 鏂板 `aris/shared/`锛岀粺涓€缁存姢 runner銆丟PU 妯℃澘銆佷骇鐗╃瓥鐣ヤ笌璇勫娓呭崟
- [x] 鏂板 `aris/tech-01-coordination/`锛屼负鍏抽敭鎶€鏈竴鎻愪緵鐙珛 brief / plan / tracker / acceptance
- [x] 鏂板 `aris/tech-02-propagation/`锛屼负鍏抽敭鎶€鏈簩鎻愪緵鐙珛 brief / plan / tracker / acceptance
- [x] 鏂板 `aris/tech-03-risk/`锛屼负鍏抽敭鎶€鏈笁鎻愪緵鐙珛 brief / plan / tracker / acceptance
- [x] 2026-05-10 `aris/tech-01-coordination/systemDesign.md` 鍗曟枃浠惰惤鐩橈紙绯荤粺璁捐 脳 MVP 脳 CCF-B+ 缁艰堪锛夛紝鍚敊浣嶇煩闃?M1鈥揗5 + ADR-001 + T1鈥揟6 鏃跺簭鍘熷垯 + M0鈥揗6 閲岀▼纰?- [ ] 浣跨敤 `aris/tech-01-coordination/` 瀹屾垚鍏抽敭鎶€鏈竴浠ｇ爜钀藉湴锛圥SL 鏂版柟鍚戯紱鏃ф柟鍚?CooRTweet 鍏变韩瀵硅薄 MVP 宸插湪 `system/`锛?- [~] 浣跨敤 `aris/tech-02-propagation/` 瀹屾垚鍏抽敭鎶€鏈簩浠ｇ爜钀藉湴锛圚ybrid TS + LLM 璺嚎锛歐P1-3 宸插畬鎴愶紝WP4-5 鏈惎鍔級
- [x] 浣跨敤 `aris/tech-03-risk/` 瀹屾垚鍏抽敭鎶€鏈笁浠ｇ爜钀藉湴锛坄core/review/` 1,340 琛?MVP + `risk_service` 缂栨帓灞傦級

---

## 妯″潡寮€鍙戣繘搴?
### 鎬昏

| 妯″潡 | 鐘舵€?| 浼樺厛绾?| 渚濊禆 |
|------|------|--------|------|
| 椤圭洰楠ㄦ灦涓庡熀纭€璁炬柦 | 鉁?宸插畬鎴?| P0 | - |
| 韬唤璁よ瘉妯″潡 | 鉁?宸插畬鎴?| P0 | 椤圭洰楠ㄦ灦 |
| 鏁版嵁閲囬泦妯″潡锛圡ock锛?| 鉁?宸插畬鎴?| P0 | 椤圭洰楠ㄦ灦 |
| 鍓嶇 - 甯冨眬涓庤璇?| 鉁?宸插畬鎴?| P0 | 鍚庣璁よ瘉妯″潡 |
| 鍓嶇 - 閲囬泦绠＄悊椤?| 鉁?宸插畬鎴?| P0 | 鍚庣閲囬泦妯″潡 |
| 鏁版嵁閲囬泦妯″潡锛堢湡瀹炵埇铏級 | 鉁?宸插畬鎴?| P1 | Mock 妯″潡瀹屾垚 |
| 缁熶竴鍒嗘瀽杩愯搴曞骇 | 鉁?鍏抽敭鎶€鏈鍙ｅ凡璐€?| P1 | 鐪熷疄鏁版嵁閲囬泦 |
| 鍗忓悓妫€娴嬫ā鍧楋紙Coordination Discover evidence runtime锛?| 鉁?宸叉帴鍏ョ粺涓€鍒嗘瀽 | P1 | 鏁版嵁閲囬泦 |
| 鍗忓悓妫€娴嬫ā鍧楋紙鍏紑妫€娴嬭瘎娴嬶級 | 馃敳 寰呭疄鐜?| P1 | Coordination Discover evidence runtime |
| 浼犳挱鐩戞帶妯″潡锛圥ropagationAnalysis hindcast protocol锛?| 鉁?宸叉帴鍏ョ粺涓€鍒嗘瀽 | P1 | 鏁版嵁閲囬泦銆佸崗鍚屾娴?|
| 浼犳挱鐩戞帶妯″潡锛圥ropagationAnalysis WP4-5 绔嬪満/鍗卞锛?| 馃敳 寰呭紑鍙?| P1 | WP1-3 |
| 璐︽埛鐩戞祴妯″潡 | 鉁?宸插畬鎴愶紙鍚?BotRHG API锛?| P1 | 鏁版嵁閲囬泦 |
| 鍓嶇 - 鍗忓悓妫€娴嬮〉锛堢綉缁滃彲瑙嗗寲锛?| 鉁?宸插畬鎴?| P1 | 鍚庣鍗忓悓妫€娴?|
| 鍓嶇 - 浼犳挱鐩戞帶椤碉紙鏃堕棿绾?瑙掕壊锛?| 鉁?宸插畬鎴?| P1 | 鍚庣浼犳挱鐩戞帶 |
| 鍓嶇 - 璐︽埛鐩戞祴椤碉紙鐢诲儚+璇勫垎锛?| 鉁?宸插畬鎴?| P1 | 鍚庣璐︽埛鐩戞祴 |
| 鍓嶇 - 鎶ュ憡鐮斿垽椤?| 鉁?宸插畬鎴?| P1 | 鍚庣鎶ュ憡鐮斿垽 |
| 鍓嶇 - UX 澧炲己锛堝瘑搴?鍒嗛〉/寮曞锛?| 鉁?宸插畬鎴?| P1 | 鍚勫墠绔〉闈?|
| Review Teacher-Student 瀹℃煡 | 鉁?runtime seam 宸叉帴鍏?| P1 | EventSnapshot銆丆oordinationDiscover銆丳ropagationAnalysis |
| 鎶ュ憡鐮斿垽妯″潡 | 鉁?MVP 宸插畬鎴?| P2 | 鍗忓悓妫€娴嬨€佷紶鎾洃鎺с€佽处鎴风洃娴?|
| 鍓嶇 - 鍒嗘瀽宸ヤ綔鍙?| 鉁?宸叉帴鍏?V2 鍏抽敭鎶€鏈緭鍑?| P1 | 缁熶竴鍒嗘瀽杩愯搴曞骇 |
| 鍓嶇 - 鐩戞祴鐪嬫澘 | 馃敡 寮€鍙戜腑锛堢湡瀹炴暟鎹?+ 鍦板浘锛?| P1 | Dashboard API銆丮ongo 浜嬩欢鏁版嵁 |
| 绯荤粺鑱旇皟涓庢祴璇?| 馃敡 閮ㄥ垎锛堟柊澧?BotRHG 鍚庣鍥炲綊娴嬭瘯锛?| P2 | 鎵€鏈夋ā鍧?|

鐘舵€佽鏄庯細馃敳 寰呭紑鍙?| 馃敡 寮€鍙戜腑 | 鉁?宸插畬鎴?| 鈴革笍 鏆傚仠 | 鉂?鍙栨秷

---

### 绗竴闃舵锛氬熀纭€鎼缓 鉁?宸插畬鎴?
#### 1.1 椤圭洰楠ㄦ灦鎼缓 鉁?
- [x] 鍚庣 FastAPI 椤圭洰鍒濆鍖栵紙鐩綍缁撴瀯銆侀厤缃鐞嗐€佹棩蹇楋級
- [x] 鍓嶇 Vue 3 椤圭洰鍒濆鍖栵紙Vite + TypeScript + Ant Design Vue锛?- [x] Docker Compose 缂栨帓锛圡ySQL + MongoDB + Redis锛?- [x] `.env` 閰嶇疆妯℃澘涓庣幆澧冨彉閲忕鐞?- [x] 鏁版嵁搴撹繛鎺ュ皝瑁咃紙MySQL SQLAlchemy, MongoDB Motor, Redis锛?- [x] Alembic 鏁版嵁搴撹縼绉婚厤缃?- [x] Celery 寮傛浠诲姟鍩虹閰嶇疆
- [x] 缁熶竴鍝嶅簲鏍煎紡銆佸紓甯稿鐞嗐€佷腑闂翠欢

#### 1.2 韬唤璁よ瘉妯″潡 鉁?
- [x] 鐢ㄦ埛琛ㄨ璁′笌妯″瀷鍒涘缓
- [x] JWT Token 璁よ瘉瀹炵幇锛堢櫥褰曘€佹敞鍐屻€佸埛鏂般€佷釜浜轰俊鎭級
- [x] 瑙掕壊鏉冮檺鎺у埗锛坅dmin / analyst / viewer锛?- [x] 鍓嶇鐧诲綍椤甸潰
- [x] 鍓嶇璺敱瀹堝崼涓?Token 绠＄悊
- [x] 娴嬭瘯锛氭敞鍐?鐧诲綍/瀵嗙爜閿欒/Token閴存潈/Token鍒锋柊

#### 1.3 鏁版嵁閲囬泦妯″潡锛圡ock 妯″紡锛?鉁?
- [x] 鐖櫕鎶借薄鍩虹被 `BaseCrawler`
- [x] MockCrawler锛氱敓鎴愬惈鍗忓悓琛屼负妯″紡鐨勬ā鎷熷井鍗氭暟鎹?- [x] DataNormalizer锛氳法骞冲彴瀛楁鏍囧噯鍖?- [x] MongoDB 瀛樺偍灞傦紙raw_posts, raw_comments 闆嗗悎锛?- [x] Celery 寮傛浠诲姟鎵ц閲囬泦
- [x] 閲囬泦鐩稿叧 API 鎺ュ彛锛堝垱寤轰换鍔?浠诲姟鍒楄〃/鏁版嵁鏌ヨ/骞冲彴鍒楄〃锛?- [x] 鍓嶇閲囬泦绠＄悊椤甸潰锛堝钩鍙伴€夋嫨銆佸弬鏁伴厤缃€佷换鍔″垪琛ㄣ€佹暟鎹煡璇級
- [x] 娴嬭瘯锛歁ock鏁版嵁鐢熸垚/鍗忓悓妯″紡楠岃瘉/Normalizer/API閴存潈

---

### 绗簩闃舵锛氭牳蹇冨姛鑳藉紑鍙?
#### 2.0 鐪熷疄鐖櫕鎺ュ叆 鉁?
- [x] 鍐呯疆 social runtime锛坄system/runtimes/social_runtime`锛?  - [x] `MediaSocialCrawler.collect()` 閫氳繃浠撳簱鍐?subprocess adapter 鎵ц runtime锛屽苟鎸?JSONL 澧為噺鎵规鍏ュ簱
  - [x] 鏀寔 `weibo` / `douyin` / `xhs`锛涙湭杩佸叆骞冲彴涓嶅嚭鐜板湪鐢熶骇骞冲彴娓呭崟
  - [x] 鐧诲綍銆丆ookie銆丯ode.js銆佷唬鐞嗐€佽瘎璁哄紑鍏冲拰鍗曞笘璇勮涓婇檺鐢变繚鐣欑殑 `MEDIACRAWLER_*` 閰嶇疆鎺у埗
- [x] 鍐呯疆 news runtime锛坄system/runtimes/news_runtime`锛?  - [x] `NewsExtractCrawler.collect()` 鐩存帴璋冪敤鍐呴儴 `ExtractorService`锛屼笉渚濊禆 HTTP 鍚庣鎴栧閮ㄦ牴璺緞
  - [x] detector 璇嗗埆 URL 骞冲彴锛屽苟淇濈暀褰撳墠娉ㄥ唽 adapter 鐨勫畬鏁存彁鍙栬兘鍔?- [x] `crawl_tasks.py` 鍙緷璧?`BaseCrawler.collect() -> CrawlBatch`锛岀粺涓€鍐欏叆甯栧瓙銆佽瘎璁哄拰 `crawl_metadata`

#### 2.0.1 缁熶竴鍒嗘瀽杩愯搴曞骇 馃敡

- [x] `EventSnapshot` 濂戠害锛氫簨浠躲€佸钩鍙般€佹牳蹇?涓婁笅鏂囨椂闂寸獥銆佽鑼冨寲鍐呭銆佽娴嬪叧绯汇€佽川閲忔姤鍛娿€乸rovenance銆佹暟鎹寚绾?- [x] `AnalysisRegistry`锛氫粠 MongoDB `raw_posts` / `raw_comments` 鏋勫缓蹇収锛屽箓绛夊啓鍏?`analysis_event_snapshots`锛屽苟娉ㄥ唽 MySQL manifest
- [x] `AnalysisRun` 鐘舵€佹満锛歚queued/running/needs_evidence/awaiting_review/completed/failed/cancelled`
- [x] V2 鍒濆鎺ュ彛锛歚/api/v2/analysis/snapshots`銆乣/runs`銆乣/runs/{run_id}`銆乣/runs/{run_id}/execute`銆乣/runs/{run_id}/events`銆乣/runs/{run_id}/events/stream`
- [x] SSE 鎭㈠锛氫娇鐢?`Last-Event-ID` 鎴?REST `after_id` 杩斿洖杩藉姞浜嬩欢
- [x] 鍒ゅ喅鐗堟湰琛ㄦ敮鎸佸悓涓€ `verdict_id` 澶氱増鏈紝鍞竴鎬ц惤鍦?`(verdict_id, version)`
- [x] `AnalysisExecutor`锛氫互 `EventSnapshot` 涓鸿緭鍏ワ紝椤哄簭璋冪敤 `CoordinationEngine.analyze`銆乣PropagationEngine.hindcast`銆乣StudentRuntime.predict`銆乣TeacherJobPort.submit` 绔彛骞跺啓鍏?run events
- [x] 灏?Coordination Discover evidence runtime 鎺ュ埌 `CoordinationEngine.analyze(snapshot, options)`锛屾浛鎹㈡棫榛樿 baseline 杈撳嚭
- [x] 灏?Propagation Analysis 浜嬩欢 bundle / checkpoint adapter / hindcast protocol 鎺ュ埌 `PropagationEngine.hindcast(snapshot, options)`锛屼笉鍐嶄緷璧栧閮?research workspace
- [x] 灏?Propagation Analysis public fixture loader銆乻plit-conformal interval 鍜?baseline registry 鍐呭寲鍒?`system/research/propagation_analysis`
- [x] 灏?Student 鍚屾 runtime 鎺ュ埌 `StudentRuntime.predict(case)`锛屾病鏈?approved checkpoint 鏃舵樉寮?`shadow_untrained` 骞跺己鍒?review
- [x] 灏?Teacher 寮傛 Celery job port 鎺ュ埌 `system/research/review_teacher` 鐨?5+1+1 advisory DAG
- [x] 鏂板 canonical verdict銆佹ā鍨嬫縺娲汇€佸洖婊氬拰涓诲姩瀛︿範娌荤悊 helper锛涙暟鎹簱妯″瀷宸插叿澶?verdict/version/feedback/activation 琛?- [~] 鍓嶇鍒嗘瀽鍛樺伐浣滄祦杩佺Щ鍒?V2 杩愯涓?SSE 鎭㈠锛歚/analysis` 宸插睍绀?Coordination Discover/Propagation Analysis/Student/Teacher 杈撳嚭锛涘畬鏁?adjudication銆乿erdict 瀹℃壒涓庢ā鍨嬫縺娲?UI 浠嶅緟瀹炵幇

#### 2.1 鍗忓悓妫€娴嬫ā鍧?鉁?
- [x] CooRTweet 鏍稿績绠楁硶 Python 閲嶅啓锛坄core/coordination_baseline/`锛?  - [x] `detect_groups()` 閲嶅啓锛氭椂闂寸獥鍙ｅ唴鍏变韩琛屼负閰嶅锛坧andas + numpy 鍚戦噺鍖栵級
  - [x] `generate_coordinated_network()` 閲嶅啓锛氬姞鏉冩棤鍚戝浘 + 鍒嗕綅鏁伴槇鍊硷紙networkx锛?  - [x] `flag_speed_share()` 閲嶅啓锛氭洿绐勬椂闂寸獥鎵撴爣
  - [x] `account_stats()` / `group_stats()` 閲嶅啓锛氳处鎴风骇/瀵硅薄绾х粺璁?- [x] 鍥惧紩鎿庢帴鍙ｏ紙NetworkX 瀹炵幇锛宍graph_to_dict` 搴忓垪鍖栵級
- [x] 鍗忓悓妫€娴?API 鎺ュ彛锛坄POST /api/v1/coordination/detect`锛?- [x] 鍓嶇鍗忓悓缃戠粶 Canvas 鍔涘鍚戝彲瑙嗗寲 + 缁熻琛ㄦ牸
- [x] 澶氳涓?evidence edge 鏋勫缓锛歎RL銆佸獟浣撱€佽瘽棰樸€佸疄浣撱€佺洰鏍囥€佸師鐢熻浆璇勮禐/鍥炲銆佽繎閲嶅鍐呭
- [x] 1h/6h/24h 50% 閲嶅彔绐楀彛銆佺ぞ鍖鸿氨绯汇€佽瘉鎹鐩栥€侀浂妯″瀷鏄捐憲鎬у拰鎵板姩椴佹鎬?- [x] `CoordinationEngine.analyze(snapshot, options) -> CoordinationResult` 浣滀负缁熶竴鍒嗘瀽鍏ュ彛
- [ ] 鏁版嵁娓呮礂鍚庢寜浜嬩欢椤哄簭杩涜鏇村畬鏁寸殑鍒嗗钩鍙板鏍革紝鍐嶅仛璺ㄥ钩鍙拌仛鍚?- [ ] 鍏紑鏁版嵁 Detect 璇勬祴锛歝ampaign/platform/time 鐣欏嚭銆丄UPRC銆丮axF1銆佹牎鍑嗗拰 5-seed 缃俊鍖洪棿
- [ ] 鍒嗗眰浜哄伐澶嶆牳宸ヤ綔鍙帮細姣忓钩鍙扮ぞ鍖烘敮鎸?鍙嶈瘉/鏃犳硶鍒ゆ柇璁板綍锛屼笉鐩存帴褰㈡垚璁粌闆?
#### 2.2 浼犳挱鐩戞帶妯″潡 鉁?
- [x] 浼犳挱瀛愬浘鏋勫缓锛堝熀浜庡叡浜璞℃椂搴忓叧绯伙紝`core/propagation.py`锛?- [x] 浼犳挱鏃堕棿绾块噸寤?- [x] 鍏抽敭瑙掕壊璇嗗埆绠楁硶锛堣捣鐖?妗ユ帴/鎵╂暎鑺傜偣锛屼粙鏁颁腑蹇冩€э級
- [x] 楂樺嵄 claim/thread 瀹氫綅涓庢帓搴?- [x] 浼犳挱鐩戞帶 API 鎺ュ彛锛坄GET /api/v1/propagation/analyze`锛?- [x] 鍓嶇浼犳挱鏃堕棿绾?+ 鍏抽敭瑙掕壊鍗＄墖 + Claim 琛ㄦ牸
- [x] Propagation Analysis 缂撳瓨璇佹嵁鍐呯疆鍒?`system/research/propagation_analysis/benchmark/`锛岀郴缁熸湇鍔′笉鍐嶈鍙?`subsystems/cogguard_dev`
- [x] `propagation_analysis_prediction_service.py` 鍒犻櫎澶栭儴 `sys.path.insert`锛屼簨浠?bundle / checkpoint adapter 鍐呯疆鍒?`system/research/propagation_analysis/benchmark/adapters/`
- [x] Propagation Analysis current-event live runtime 宸叉帴閫氾紝骞剁敱 `propagation_analysis-hindcast-protocol-v1` 鍖呰涓虹粺涓€棰勬祴鍗忚
- [x] 鍏紑 fixture loader銆丒ventSnapshot bundle adapter銆?0/95 split-conformal 鍖洪棿銆佷笅涓€璺?ranking 鍜屽钩鍙?hindcast 宸插唴缃?- [x] EdgeBank銆丠awkes-recency銆乸ersistence銆乭istorical-mean baseline registry 宸插唴缃紱TGN/DyGFormer/CasFlow/CasFT checkpoint slot 鏄惧紡杩斿洖缂?checkpoint/涓嶅彲鐢?- [ ] 椤甸潰鍛藉悕鐢扁€滀紶鎾綊鍥犫€濊皟鏁翠负鈥滀紶鎾洃鎺р€?- [ ] 鐩稿叧鍙戝笘鐢ㄦ埛妫€娴嬩笌楂樺奖鍝嶅姏鑺傜偣璇嗗埆鐨勭爺绌剁骇璇勪及
- [ ] 鍙儴缃?TGN/DyGFormer/CasFlow/CasFT checkpoint runtime 涓庡叕寮€ benchmark 璁粌/璇勬祴 runner

#### 2.3 璐︽埛鐩戞祴妯″潡 鉁?
- [x] 璐︽埛琛屼负鐢诲儚鏋勫缓锛坄core/account_profiler.py`锛?  - [x] 鍙戞枃棰戠巼銆侀棿闅旂粺璁°€佷綔鎭妭寰嬶紙24h 鐩存柟鍥撅級
  - [x] 浜掑姩妯″紡锛堢偣璧?杞彂/璇勮姹囨€伙級
  - [x] 鍐呭澶氭牱鎬э紙鏍囩/URL 缁熻锛?- [x] 鑷姩鍖栧€惧悜璇勪及绠楁硶锛?-100 鍒嗭紝澶氱淮搴︾患鍚堣瘎鍒嗭級
- [x] 璐︽埛鐩戞祴 API 鎺ュ彛锛坄GET /api/v1/accounts/profiles`銆乣GET /api/v1/accounts/detail/{id}`锛?- [x] BotRHG 椋庢牸绀句氦鏈哄櫒浜烘娴?API锛坄POST /api/v1/accounts/bot-detection`锛夛細浠庡凡閲囬泦甯栧瓙鏋勯€?profile/text/activity 鐗瑰緛銆並NN 鏀寔瓒呰竟鍜屽眬閮ㄥ彲闈犳€ц矾鐢憋紝瀵逛綆鍙潬璐﹀彿鎵ц閫夋嫨鎬ф畫宸慨姝ｅ苟杩斿洖 base/final bot 姒傜巼涓庤В閲婅瘉鎹?- [x] 鍓嶇璐︽埛鐢诲儚鍒楄〃椤碉紙璇勫垎鎺掑簭銆佽繘搴︽潯鐫€鑹诧級
- [ ] 鍗曚釜鐢ㄦ埛涓婚〉閲囬泦锛氭敮鎸佷富椤甸摼鎺?鐢ㄦ埛 ID锛屾敹闆嗕富椤靛厓鏁版嵁涓庡叏閮ㄥ彂鏂?- [ ] 璐︽埛璇︽儏椤碉細鏌ョ湅鐢ㄦ埛涓婚〉銆佸叏閮ㄥ唴瀹广€佸唴瀹归闄?绔嬪満/妯℃澘鍖栨娴嬬粨鏋?- [ ] 鍘嗗彶鍙備笌杩借釜
- [ ] NLP 鑳藉姏寤鸿锛堜腑鏂囨枃鏈悜閲忓寲銆佽涔夌浉浼煎害銆佹儏鎰熷垎鏋愶級

#### 2.4 鍓嶇 UX 澧炲己 鉁?
- [x] 渚ц竟鏍忓惎鐢ㄥ崗鍚屾娴嬨€佷紶鎾洃鎺с€佽处鎴风洃娴?- [x] 鐧诲綍椤靛鍔犳敞鍐岃〃鍗曞垏鎹?- [x] 閲囬泦浠诲姟鍒楄〃澧炲姞鍒犻櫎/鍙栨秷鎿嶄綔
- [x] 渚ц竟鏍忔ā鍧楁偓娴弿杩版彁绀?- [x] 鍚勬ā鍧楀垵濮嬪紩瀵艰鏄庝笌缁熻姒傝
- [x] 鏁版嵁琛ㄦ牸瀵嗗害鍒囨崲锛堢揣鍑?涓瓑/瀹芥澗锛? 姣忛〉鏉℃暟鍙€夛紙10/30/50/100锛?
---

### 绗笁闃舵锛氱爺鍒や笌闆嗘垚

#### 3.0 Review Teacher-Student 瀹℃煡 鉁?runtime seam 宸插畬鎴?
- [x] `system/runtimes/review_student/`锛氬悓姝?`StudentRuntime.predict(case)`锛岃緭鍑?preliminary verdict銆乆LM-R-base / frozen multimodal / gating / MIL / community GNN 鏋舵瀯濂戠害銆佷富鍔ㄥ涔犱俊鍙峰拰钂搁璁″垝
- [x] `system/research/review_teacher/`锛?+1+1 Teacher DAG锛坈laim planning銆乼rusted retrieval銆乼ext verification銆乵ultimodal verification銆乭arm/stance/analysis capability context銆丟old aggregator銆乨isagreement-only Critic/Judge锛?- [x] `app.core.analysis.governance`锛歝anonical approval銆乵odel activation銆乺ollback銆乤ctive-learning batch helper
- [x] Teacher 鍙敓鎴?`teacher_advisory`锛孲tudent 鍙敓鎴?`preliminary`锛沜anonical 鍙兘鏉ヨ嚜鍒嗘瀽鍛樺鎵?- [ ] 鐪熷疄澶氭ā鍨嬫棌鍦ㄧ嚎 Teacher provider銆佸彲淇℃绱?provider 鍜屽妯℃€佹牳楠?provider
- [ ] approved feedback / Teacher traces 钂搁璁粌 runner 涓?Student approved checkpoint
- [ ] adjudication UI銆佹ā鍨嬬増鏈樊寮?UI銆乤ctive pointer 婵€娲?鍥炴粴 UI

#### 3.1 鎶ュ憡鐮斿垽妯″潡 鉁?MVP 宸插畬鎴?
- [x] 涓夌淮璇勪及寮曟搸锛堢湡瀹炴€?鎿嶇旱鎬?鍗卞鎬э級鈥?`core/review/ds_fusion.py` (234 琛?
- [x] DISARM 鎴樻湳鏄犲皠 + 鏀诲嚮璺緞璇勫垎 鈥?`core/review/disarm_scorer.py` (381 琛?
- [x] 浼犳挱闃舵妫€娴?鈥?`core/review/phase_detector.py` (169 琛?
- [x] 澶氭簮璇佹嵁姹囪仛涓庤瘉鎹摼 鈥?`core/review/evidence_builder.py` (244 琛?
- [x] 缁撴瀯鍖栫爺鍒ゆ姤鍛婄敓鎴?鈥?`core/review/report_builder.py` (278 琛?
- [x] 鎶ュ憡鐮斿垽鏈嶅姟灞?鈥?`services/risk_service.py` (153 琛?
- [x] 鎶ュ憡鐮斿垽 API 鈥?`api/v1/risk.py` (68 琛?
- [x] 鍓嶇鐮斿垽宸ヤ綔鍙?鈥?`frontend/src/views/risk/index.vue`
- [ ] 鏁版嵁搴撹縼绉昏ˉ榻愶紙`models/risk_assessment.py` 50 琛屽凡寤烘ā鍨嬶紝缂?alembic 杩佺Щ锛夆殸锔?閮ㄧ讲闃诲
- [ ] LLM 妗ユ帴 `core/review/llm_bridge.py`锛堝綋鍓?30 琛?stub锛岄渶琛?LLM 瀹㈡埛绔緷璧栵級

#### 3.2 棰勮绠＄悊 馃敳

- [ ] 棰勮瑙勫垯閰嶇疆
- [ ] 浜嬩欢绾?/ 缇や綋绾?/ claim 绾у憡璀?- [ ] 鍛婅鐘舵€佺鐞?- [ ] 鍓嶇棰勮涓績椤甸潰

#### 3.3 鐩戞祴鐪嬫澘 馃敡

- [x] 鏂板 Dashboard API 鑱氬悎 MongoDB 浜嬩欢鏁版嵁锛堥粯璁?`trump_visit_2026_05_21`锛?- [x] 鍓嶇缁熻鍗＄墖鎺ュ叆鐪熷疄 posts/comments/platform/risk report 鏁版嵁
- [x] ECharts 涓栫晫鍦板浘灞曠ず浜嬩欢浣嶇疆锛屾寜绗竴鍙戝笘鑰?IP 灞炲湴瀹氫綅
- [x] 骞冲彴鏁版嵁缁熻涓庝簨浠跺畾浣嶆槑缁嗚〃
- [ ] 鐑偣浜嬩欢鎺掕
- [ ] 椋庨櫓瓒嬪娍鍥捐〃锛圗Charts锛?
#### 3.4 鎶ュ憡涓績 馃敳

- [ ] 鎶ュ憡鍒楄〃涓庤鎯?- [ ] 鎶ュ憡瀵煎嚭锛圥DF / JSON锛?- [ ] 妗堜緥褰掓。

---

### 绗洓闃舵锛氭祴璇曚笌浼樺寲

#### 4.1 鍔熻兘娴嬭瘯 馃敳

- [ ] 鍚庣 API 鍏ㄦā鍧楅泦鎴愭祴璇?- [ ] 鐖櫕灏佽闆嗘垚娴嬭瘯
- [ ] 鍗忓悓妫€娴嬬畻娉曟纭€ч獙璇侊紙瀵圭収 CooRTweet R 鍖呯粨鏋滐級
- [ ] 鍓嶇缁勪欢娴嬭瘯
- [ ] 绔埌绔祴璇?
#### 4.2 鎬ц兘浼樺寲 馃敳

- [ ] 鏁版嵁搴撴煡璇紭鍖?- [ ] 澶ц妯℃暟鎹鐞嗘€ц兘
- [ ] 鍓嶇鍔犺浇鎬ц兘
- [ ] Celery 浠诲姟骞跺彂浼樺寲

#### 4.3 閮ㄧ讲涓庢枃妗?馃敳

- [ ] 鍚庣 Dockerfile
- [ ] 鍓嶇 Dockerfile
- [ ] 鍏ㄦ爤 Docker Compose 涓€閿儴缃?- [ ] 鐢ㄦ埛鎿嶄綔鎵嬪唽

---

## 宸查€氳繃鐨勬祴璇?
| 娴嬭瘯 | 璇存槑 | 鐘舵€?|
|------|------|------|
| `test_health_check` | 鍚庣鍋ュ悍妫€鏌ユ帴鍙?| 鉁?閫氳繃 |
| `test_mock_crawler_generates_posts` | MockCrawler 鐢熸垚甯栧瓙鏁版嵁 | 鉁?閫氳繃 |
| `test_mock_crawler_generates_comments` | MockCrawler 鐢熸垚璇勮鏁版嵁 | 鉁?閫氳繃 |
| `test_mock_crawler_coordinated_pattern` | Mock 鏁版嵁鍖呭惈鍗忓悓琛屼负妯″紡 | 鉁?閫氳繃 |
| `test_normalizer_standardizes_weibo_post` | 寰崥甯栧瓙瀛楁鏍囧噯鍖?| 鉁?閫氳繃 |
| `test_normalizer_standardizes_comment` | 璇勮瀛楁鏍囧噯鍖?| 鉁?閫氳繃 |
| `test_list_platforms` | 骞冲彴鍒楄〃鎺ュ彛 | 鉁?閫氳繃 |
| `test_mediacrawler_env` | MediaCrawler 鐨?`.env` / `uv` / `node` 瑙ｆ瀽 | 鉁?閫氳繃 |
| `test_analysis_coordination_discover_runtime` | Coordination Discover evidence runtime锛氬琛屼负杈广€佺獥鍙ｃ€佽氨绯汇€侀浂妯″瀷銆佹壈鍔ㄩ瞾妫掓€?| 鉁?閫氳繃 |
| `test_propagation_analysis_prediction_service` | Propagation Analysis 鍐呯疆 loader銆乭indcast protocol銆乧onformal銆乥aseline registry | 鉁?閫氳繃 |
| `test_analysis_review_runtime` | Review Student/Teacher/governance seam | 鉁?閫氳繃 |
| 鍚庣鍏ㄩ噺娴嬭瘯 | `python -m pytest -q` | 鉁?361 passed, 27 skipped |
| `test_register_success` | 鐢ㄦ埛娉ㄥ唽 | 鉁?閫氳繃锛堥渶 MySQL锛?|
| `test_register_duplicate_username` | 閲嶅鐢ㄦ埛鍚嶆敞鍐?| 鉁?閫氳繃锛堥渶 MySQL锛?|
| `test_login_success` | 鐢ㄦ埛鐧诲綍 | 鉁?閫氳繃锛堥渶 MySQL锛?|
| `test_login_wrong_password` | 閿欒瀵嗙爜鐧诲綍 | 鉁?閫氳繃锛堥渶 MySQL锛?|
| `test_profile_with_token` | Token 閴存潈璁块棶 | 鉁?閫氳繃锛堥渶 MySQL锛?|
| `test_profile_without_token` | 鏃?Token 鎷掔粷璁块棶 | 鉁?閫氳繃 |
| `test_refresh_token` | Token 鍒锋柊 | 鉁?閫氳繃锛堥渶 MySQL锛?|
| 鍓嶇鏋勫缓 | `npm run build`锛坄vue-tsc -b && vite build`锛?| 鉁?閫氳繃 |

---

## 寰呭喅璁簨椤癸紙鍚庣画锛?
| 缂栧彿 | 浜嬮」 | 璇存槑 | 鐘舵€?|
|------|------|------|------|
| T-01 | Neo4j 鎺ュ叆 | 褰撳墠鐢?NetworkX 鍐呭瓨鍥惧垎鏋愶紝鍚庣画鍙垏鎹㈠埌 Neo4j | 馃搵 寰呭畾 |
| T-02 | LLM 鎺ュ叆 | 鎶ュ憡鐮斿垽妯″潡棰勭暀浜嗘帴鍙ｏ紝鍙帴鍏ラ€氫箟鍗冮棶/鏅鸿氨/DeepSeek | 馃搵 寰呭畾 |
| T-03 | DISARM 鎴樻湳鏄犲皠 | 灏嗘搷绾佃涓烘槧灏勪负 DISARM tactics/techniques | 馃搵 寰呭畾 |
| T-04 | 绾夸笂閮ㄧ讲 | 褰撳墠鏈湴閮ㄧ讲锛屽悗缁彲浜戞湇鍔″櫒閮ㄧ讲 | 馃搵 寰呭畾 |
| T-05 | 鏇村骞冲彴鏀寔 | 褰撳墠浠?Mock 寰崥锛岄€愭鎺ュ叆鐪熷疄骞冲彴 | 馃搵 寰呭畾 |
| T-06 | 妯″瀷璁粌涓庡井璋?| 浣跨敤鍏紑鏁版嵁闆嗗井璋?NLP 妯″瀷 | 馃搵 寰呭畾 |
| T-07 | GPU 鐜閫傞厤 | NLP 妯″瀷鎺ㄧ悊鍔犻€?| 馃搵 寰呭畾 |

---

## 鍙傝€冭祫鏂?
- [鐜鎼缓鎸囧崡](environment-setup.md) - Docker銆丳ython銆丯ode.js 瀹夎涓庨厤缃?- [寮€鍙戝彉鏇存棩蹇梋(development-log.md) - 寮€鍙戣繃绋嬪彉鏇磋褰曪紝涓庢湰鏂囨。鍚屾缁存姢
- [ARIS 宸ヤ綔绌洪棿鍏ュ彛](../aris/README.md) - 涓夋潯鍏抽敭鎶€鏈殑鐙珛鎵ц鍏ュ彛
- [鎶€鏈儗鏅€昏](research/key-technology-background/overview.md) - 浠庡紑棰樻姤鍛婁笌鐜版湁浠ｇ爜鎻愮偧鐨勯暱鏈熻儗鏅枃妗?- [绯荤粺寮€鍙戞枃妗(../../system/README.md) - 鐩綍缁撴瀯銆丄PI銆侀儴缃层€佹祴璇曘€佷娇鐢ㄦ柟寮?- [BotRHG 绀句氦鏈哄櫒浜烘娴嬫帴鍏ヨ鍒抅(botrhg-social-bot-detection-plan.md) - 鍚庣 API銆佹柟娉曞绾︿笌鐮旂┒杈圭晫
- [寮€棰樻姤鍛奭(../../materials/寮€棰樻姤鍛?doc) - 椤圭洰鑳屾櫙銆佸垱鏂版€у垎鏋愩€佸姛鑳借鏄庛€佹妧鏈矾绾?- [MediaCrawler](../MediaCrawler-main/README.md) - 绀句氦濯掍綋鐖櫕鍙傝€?- [NewsCrawler](../NewsCrawler-main/README.md) - 鏂伴椈鐖櫕鍙傝€?- [CooRTweet](../CooRTweet-master/README.md) - 鍗忚皟琛屼负妫€娴嬬畻娉曞弬鑰?
