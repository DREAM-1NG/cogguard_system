# CogGuard research / engineering 鍒嗗伐鎬昏

> **鐢ㄩ€?*锛氫綔涓哄悗缁洟闃熷垎宸ョ殑鏉冨▉鍒嗗壊琛ㄣ€傛妸涓夊ぇ鏍稿績鍔熻兘锛團-COORD / F-PROP / F-RISK锛? 妯悜鏀拺鍔熻兘锛團-ACCT锛夋寜"绠楁硶鍒涙柊锛坮esearch锛?涓?宸ョ▼鎷艰锛坋ngineering锛?浜屽垎锛屾槑纭摢浜涗换鍔＄敱 Claude Code 鍦ㄦ湰浠撳簱蹇€熷畬鎴愩€佸摢浜涗换鍔￠渶瑕佹湰鍦板疄楠屾帰绌躲€?> **缁存姢瑙勫垯**锛氭瘡鏉?research 浠诲姟瀹屾垚鏈湴瀹為獙浜у嚭鍚庯紝瑕佸洖鍐欏弬鏁?/ 缁撹鍒板搴?`aris/tech-NN/REQUIREMENTS.md` 鎴?`doc/engineering/F-ACCT-account-profiling.md`锛涙瘡鏉?engineering 浠诲姟瀹屾垚鎻愪氦鍚庯紝瑕佸嬀閫夌姸鎬佸苟鍚屾 `development-log.md`銆?> **鏈€鍚庢洿鏂?*锛?026-05-20

---

## 涓€銆佸姛鑳芥灦鏋勪笌涓昏鎶€鏈搴旇〃

CogGuard 涓婚摼璺細`浜嬩欢 鈫?璇佹嵁 鈫?鍗忓悓 鈫?浼犳挱 鈫?椋庨櫓 鈫?澶勭疆`銆?
**涓夊ぇ鏍稿績鍔熻兘**鍚勭敱涓€椤瑰叧閿妧鏈紙analysis capability锛夋敮鎾戯紝**涓€椤规í鍚戞敮鎾戝姛鑳斤紙F-ACCT锛?*琚笁澶у姛鑳藉叡鍚屾秷璐广€?
```
                鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?                鈹?    F-ACCT 娣卞害璐﹀彿鐢诲儚锛堟í鍚戞敮鎾戯級    鈹?                鈹? bot / stance 鑱氬悎 / KOL / activity   鈹?                鈹斺攢鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?                     鈹?          鈹?          鈹?                     鈻?          鈻?          鈻?                  F-COORD    F-PROP      F-RISK
                  (Coordination Discover PSL)  (Propagation Analysis CSw)  (Review PA-H+DISARM)
```

| 鍔熻兘绠€绉?| 涓枃鍚?| 绫诲瀷 | 涓昏鎶€鏈紙鍒涙柊杞戒綋锛?| 鍏朵粬鎶€鏈敮鎸?| 绯荤粺浣嶇疆 |
|---|---|---|---|---|---|
| **F-COORD** | 璺ㄥ钩鍙板崗鍚屾娴?| 鏍稿績 | Coordination Discover PSL锛圥air Surprisal Layer锛?| CooRTweet 鍏变韩瀵硅薄銆佺粺璁℃楠屻€佽涔夊悜閲忋€佸浘绠楁硶銆丒Charts | `core/coordination_baseline/` + `aris/tech-01-coordination/` |
| **F-PROP** | 浼犳挱鐩戞帶涓庤秼鍔块娴?| 鏍稿績 | Propagation Analysis CascadeSwitch锛堜綋鍒跺垏鎹㈤娴嬶級 | 鏃跺簭鐗瑰緛宸ョ▼銆丩LM API銆佺珛鍦?鍗卞璇勪及锛堝笘绾э級銆佹贩鍚堥娴嬨€佸彲瑙嗗寲 | `core/propagation/` + `aris/tech-02-propagation/` |
| **F-RISK** | 鎶ュ憡鐮斿垽涓庢敾鍑昏矾寰?| 鏍稿績 | Review Phase-Aware Hazard + DISARM 璺緞鎺ㄧ悊 | Dempster-Shafer 铻嶅悎銆佽瘉鎹壒寰併€丏ISARM 鏄犲皠銆佹姤鍛婃ā鏉裤€佽鍒欏紩鎿?| `core/review/` + `aris/tech-03-risk/` |
| **F-ACCT** | 娣卞害璐﹀彿鐢诲儚 | **鏀拺** | 棰勮缁?Bot 妫€娴嬶紙Botometer / Twibot-22 RoBERTa锛?| 璐﹀彿绾?stance 鑱氬悎銆佽鍒欏寲 KOL 璇嗗埆銆佽涓虹敾鍍忋€佷綔鎭妭寰?| `core/account/` + `doc/engineering/F-ACCT-account-profiling.md` |

---

## 浜屻€佺爺绌?vs 宸ョ▼鐨勫垽瀹氳鍒?
| 鏍囩 | 鍒ゅ畾鏉′欢锛堟弧瓒冲叾涓€鍗冲綊鍏ワ級 |
|---|---|
| **research** | (1) 鍙傛暟闇€璋冿紝鏁堟灉涓嶇‘瀹氾紱(2) 闇€瑕佹秷铻嶅疄楠屾垨鏁版嵁闆嗛獙璇侊紱(3) 鏈夎鏂囨柊棰栨€э紝鍙啓鏂囩珷锛?4) 绠楁硶閫夋嫨鏈韩浠嶅湪姣旇緝涓紙鍚?LLM prompt 宸ョ▼锛?|
| **engineering** | (1) 杈撳叆杈撳嚭瑙勮寖鏄庣‘锛?2) 鍏紡 / 绠楁硶 / 妯℃澘宸茬粡纭畾锛屾寜瑙勬牸鍐欏氨鑳借窇锛?3) 璺戝嚭鏉ョ粨鏋滃彲棰勬湡锛?4) 澶辫触妯″紡涓嶆潵鑷畻娉曟湰韬€屾潵鑷泦鎴?|
| **杈圭晫** | 鍚屾椂婊¤冻涓よ竟閮ㄥ垎鏉′欢锛堝 LLM 绔嬪満妫€娴嬧€斺€旀棦闇€瑕?prompt 璋冧紭鍙堟湁澶ч噺宸ョ▼鎺ュ叆锛?|

---

## 涓夈€丗-COORD锛堣法骞冲彴鍗忓悓妫€娴嬶級鎷嗗垎

### 3.1 涓昏鎶€鏈細Coordination Discover PSL锛堝叏閮?research锛?
| 瀛愰」 | 绠€杩?| 鏍囩 | 褰撳墠鐘舵€?| 钀界偣 / 闃诲 |
|---|---|---|---|---|
| 瀵圭О鍙岃处鍙疯秴鍑犱綍妫€楠?| `p_pair = max(p_u, p_v)` 鏍℃娲昏穬搴﹀樊寮?| research | 鏈紑濮?| `core/coordination_baseline/significance.py`锛岄渶娑堣瀺瀵规瘮 max / min / product |
| Cauchy combination | 铻嶅悎澶?object / 澶氶€氶亾 p-values锛堟棤鐙珛鎬у亣璁撅級 | research | 鏈紑濮?| 鍚屼笂 |
| Pair-level BH-FDR | 閰嶅灞傜骇澶氶噸妫€楠屾牎姝?| research | 鏈紑濮?| 鍚屼笂锛岄渶 permutation-based FDR 鏍″噯 |
| 澶氶€氶亾璇佹嵁铻嶅悎 | Object / Semantic / Cascade 閫氶亾鏉冮噸 | research | 鏈紑濮?| 鍚屼笂 + `channels.py` |
| ADR-001 瑙﹀彂鏉′欢 | 澶氭ā鎬佹墿灞曡Е鍙戯紙铻嶅悎 FDR > 0.2锛?| research | 璁捐瀹屾垚 | `systemDesign.md` 宸茶璁★紝浠ｇ爜渚ф棤 |

### 3.2 鍏朵粬鎶€鏈敮鎸?
| 瀛愰」 | 绠€杩?| 鏍囩 | 褰撳墠鐘舵€?| 钀界偣 |
|---|---|---|---|---|
| CooRTweet 鍏变韩瀵硅薄妫€娴?| 鏃堕棿绐楀唴閰嶅銆佸揩绐楁爣璁?| engineering | 鉁?宸插疄鐜?| `core/coordination_baseline/detector.py` (177) |
| 澶氶€氶亾 Object 鎻愬彇 | url / hashtag / media / cascade 鈫?object_id | engineering | 鏈紑濮?| `core/coordination_baseline/channels.py` |
| 璇箟鍚戦噺缂栫爜 | 鍐荤粨鍙ュ悜閲?+ mutual-kNN | 杈圭晫 | 鏈紑濮?| `semantic.py`锛堟ā鍨嬮€夋嫨鏄爺绌躲€佽皟鐢ㄦ槸宸ョ▼锛?|
| statsmodels BH-FDR 璋冪敤 | 鐜版垚鍖呭寘瑁?| engineering | 鏈紑濮?| `significance.py` 鍐?|
| 鍗忓悓鍥捐仛鍚?| NetworkX 鍔犳潈鍥?/ 杩為€氬垎閲?/ 绀惧尯 | engineering | 鉁?宸插疄鐜?| `core/coordination_baseline/network.py` (166) |
| 鍗忓悓妫€娴?API | `POST /api/v1/coordination/detect` | engineering | 鉁?宸插疄鐜?| `api/v1/coordination.py` (27) |
| 鏈嶅姟灞傜紪鎺?| 涓茶仈閫氶亾鎻愬彇 鈫?PSL 鈫?缃戠粶鑱氬悎 | engineering | 闆忓舰 | `services/coordination_service.py` (90, 寰呮墿) |
| 鍓嶇鍗忓悓缃戠粶鍙鍖?| ECharts force-directed | engineering | 鉁?宸插疄鐜?| `frontend/src/views/coordination/index.vue` |
| 澶氭ā鎬佸睍绀烘壙杞斤紙M1锛?| 鏂囨湰/鍥剧墖/瑙嗛/澶栭摼/鍏冩暟鎹?5 瑕佺礌鍚屽睆 | engineering | 鏈紑濮?| 鍓嶇鎼滅储瀛愮郴缁?C2锛屽緟鏂板 |

璇﹁ [aris/tech-01-coordination/REQUIREMENTS.md](../../aris/tech-01-coordination/REQUIREMENTS.md)銆?
---

## 鍥涖€丗-PROP锛堜紶鎾洃鎺т笌瓒嬪娍棰勬祴锛夋媶鍒?
### 4.1 涓昏鎶€鏈細Propagation Analysis CascadeSwitch

| 瀛愰」 | 绠€杩?| 鏍囩 | 褰撳墠鐘舵€?| 钀界偣 / 闃诲 |
|---|---|---|---|---|
| 4 浣撳埗娣峰悎棰勬祴 | Seeding/Amplification/Peak/Decay 鍙傛暟鍖栨ā鍨?| research | 鉁?浠ｇ爜宸插疄鐜?| `regime_model.py` (224)锛岄渶 DeepHawkes/CasFlow 鏍″噯 |
| 浣撳埗鍚庨獙璁＄畻 | `p(z) = softmax((W路e + b) / 蟿)` | research | 鉁?浠ｇ爜宸插疄鐜?| `trend_predictor.py` (180)锛學/b/蟿 榛樿鍊兼湭鏍″噯 |
| LLM 浜嬩欢涓婁笅鏂囨彁鍙?| 6 绫讳簨浠剁被鍨?prompt + JSON Schema | research锛坧rompt锛?| 鉁?浠ｇ爜宸插疄鐜?| `llm_context.py` (162)锛宲rompt 闇€杩唬 |
| 涓嶇‘瀹氭€т及璁?| 娣峰悎鏂瑰樊 `蟽虏(t) = 危 p(z)路[f_z虏 + 蟽_z虏] - 欧虏` | research | 鉁?浠ｇ爜宸插疄鐜?| `trend_predictor.py` 鍐?|
| 绔嬪満妫€娴嬶紙WP4锛?| LLM 闆舵牱鏈垎绫?+ 6 绫荤珛鍦烘爣绛?| 杈圭晫 | 鉂?鏂囦欢涓嶅瓨鍦?| `stance_detector.py`锛岄渶鍏堝畾鏍囩浣撶郴 |
| 鍗卞鎬ц瘎浼帮紙WP5锛?| 瑙勫垯 + LLM 澧炲己鐨?0-100 璇勫垎 | 杈圭晫 | 鉂?鏂囦欢涓嶅瓨鍦?| `harm_assessor.py`锛岄渶鍏堝畾璇勫垎缁村害 |

### 4.2 鍏朵粬鎶€鏈敮鎸?
| 瀛愰」 | 绠€杩?| 鏍囩 | 褰撳墠鐘舵€?| 钀界偣 |
|---|---|---|---|---|
| 鏃跺簭鐗瑰緛宸ョ▼ | volume/velocity/acceleration/burst_zscore | engineering | 鉁?宸插疄鐜?| `ts_features.py` (107) |
| 绾ц仈褰㈡€佷簨浠舵娴?| 鏃?LLM 鏃朵粠绾ц仈鍔ㄦ€佹帹鏂紙瑙勫垯鍖栭檷绾э級 | engineering | 鏈紑濮?| `cascade_events.py` 寰呮柊澧?|
| LLM API 瀹㈡埛绔?| openai/dashscope 寮傛 + 閲嶈瘯 + mock | engineering | 鉂?缂轰緷璧?| `llm_client.py` 寰呮柊澧烇紝`pyproject.toml` 寰呰ˉ |
| 鏃ф柟鍚戞簮澶磋拷婧?| MultiDiGraph + 璇佹嵁閾?+ 鍏抽敭璺緞 | engineering | 鉁?淇濈暀 | `core/propagation_legacy.py` |
| 浼犳挱鐩戞帶 API | `GET /api/v1/propagation/analyze` | engineering | 闆忓舰 | `api/v1/propagation.py` (29, 寰呮墿) |
| 鏈嶅姟灞傜紪鎺?| 涓茶仈 ts_features 鈫?llm_context 鈫?trend_predictor | engineering | 闆忓舰 | `propagation_service.py` (48, 寰呮墿) |
| 鍓嶇浼犳挱棰勬祴鍙鍖?| 鏃跺簭鏇茬嚎 + 缃俊鍖洪棿甯?+ 浣撳埗姒傜巼鍫嗗彔鍥?| engineering | 鍩虹椤靛凡鏈?| `frontend/src/views/propagation/index.vue` |

璇﹁ [aris/tech-02-propagation/REQUIREMENTS.md](../../aris/tech-02-propagation/REQUIREMENTS.md)銆?
---

## 浜斻€丗-RISK锛堟姤鍛婄爺鍒や笌鏀诲嚮璺緞锛夋媶鍒?
### 5.1 涓昏鎶€鏈細Review Phase-Aware Hazard + DISARM

| 瀛愰」 | 绠€杩?| 鏍囩 | 褰撳墠鐘舵€?| 钀界偣 / 闃诲 |
|---|---|---|---|---|
| 5 鐘舵€佺敓鍛藉懆鏈?+ logistic hazard | seed 鈫?synchronize 鈫?breakout 鈫?saturation 鈫?regeneration | research锛? 鍙傛暟锛?| 鉁?浠ｇ爜宸插疄鐜?| `phase_detector.py` (169)锛屽弬鏁版湭鏍″噯 |
| Dempster-Shafer 涓夌淮铻嶅悎 | 鐪熷疄鎬?鎿嶇旱鎬?鍗卞鎬?+ 闃舵璋冨埗 + 鍐茬獊璐ㄩ噺 | research锛?+5 鍙傛暟锛?| 鉁?浠ｇ爜宸插疄鐜?| `ds_fusion.py` (234)锛岄渶杈圭晫 case 娴嬭瘯 |
| DISARM 鏀诲嚮璺緞鎺ㄧ悊 | 18 鏉¤竟 + 杞崲姒傜巼 + 涓嬩竴姝ラ娴?+ 鍙嶅埗寤鸿 | research锛?8 姒傜巼锛?| 鉁?浠ｇ爜宸插疄鐜?| `disarm_scorer.py` (381)锛屾鐜囦负棰嗗煙鍏堥獙 |
| 闃舵鎰熺煡鍐茬獊妫€娴?| conflict_mass > 0.3 瑙﹀彂浜哄伐浠嬪叆 | research | 鉁?浠ｇ爜宸插疄鐜?| `ds_fusion.py` 鍐?|
| 璺緞璇勫垎 | depth/breadth/completeness 鍔犳潈 | research锛? 鍙傛暟锛?| 鉁?浠ｇ爜宸插疄鐜?| `disarm_scorer.py` 鍐?|

### 5.2 鍏朵粬鎶€鏈敮鎸?
| 瀛愰」 | 绠€杩?| 鏍囩 | 褰撳墠鐘舵€?| 钀界偣 |
|---|---|---|---|---|
| 璇佹嵁鐗瑰緛鎻愬彇 | Gini/Shannon/绐佸彂鎬х瓑閫氱敤鍏紡 | engineering | 鉁?宸插疄鐜?| `evidence_builder.py` (244) |
| DISARM 鎶€鏈槧灏勮鍒欒〃 | 45 绉嶆妧鏈‖缂栫爜鏄犲皠 | engineering | 鉁?宸插疄鐜?| `disarm_scorer.py` 鍐咃紙闇€涓撳鏍￠獙锛?|
| 缁撴瀯鍖栨姤鍛?JSON 妯℃澘 | 18 椤跺眰瀛楁 + 璇佹嵁閾?+ 椋庨櫓鍥犲瓙 + 寤鸿 | engineering | 鉁?宸插疄鐜?| `report_builder.py` (278) |
| LLM 妗ユ帴 | 鎶ュ憡瑙ｉ噴鐢熸垚 + 鍙嶅埗寤鸿鑷劧璇█鍖?| engineering | 鉂?stub | `llm_bridge.py` (30, 寰呰ˉ) |
| 鎶ュ憡鐮斿垽 API | `POST /api/v1/risk/assess` + 鎶ュ憡鍒楄〃/璇︽儏 | engineering | 鉁?宸插疄鐜?| `api/v1/risk.py` (68) |
| 鏈嶅姟灞傜紪鎺?| 涓茶仈 evidence 鈫?phase 鈫?fusion 鈫?DISARM 鈫?report | engineering | 鉁?宸插疄鐜?| `risk_service.py` (153) |
| 鏁版嵁搴撴寔涔呭寲 | RiskAssessment 琛?+ alembic 杩佺Щ | engineering | 鈿狅笍 缂鸿縼绉?| `alembic/versions/xxx_add_risk.py` 寰呮柊澧?|
| 鍓嶇鎶ュ憡鐮斿垽椤?| 鎶ュ憡鍒楄〃 + 璇︽儏 + DISARM 璺緞鍙鍖?| engineering | 鍩虹椤靛凡鏈?| `risk/index.vue`锛堣矾寰勫浘寰呰ˉ锛?|

璇﹁ [aris/tech-03-risk/REQUIREMENTS.md](../../aris/tech-03-risk/REQUIREMENTS.md)銆?
---

## 浜攂is銆丗-ACCT锛堟繁搴﹁处鍙风敾鍍忥紝妯悜鏀拺鍔熻兘锛夋媶鍒?
> **瀹氫綅鎻愰啋**锛欶-ACCT 涓嶆槸绗?4 涓叧閿妧鏈紝鑰屾槸琚?F-COORD / F-PROP / F-RISK 鍏卞悓娑堣垂鐨勬í鍚戣瘉鎹眰銆?
### 5bis.1 涓昏鎶€鏈細Bot 妫€娴嬮璁粌妯″瀷

| 瀛愰」 | 绠€杩?| 鏍囩 | 褰撳墠鐘舵€?| 钀界偣 / 闃诲 |
|---|---|---|---|---|
| Botometer X API 璋冪敤 | 宸ヤ笟鍩虹嚎锛屽噯纭巼楂橈紝闇€ RAPIDAPI_KEY | engineering | 鏈紑濮?| `core/account/bot_detector.py`锛堝緟鏂板锛?|
| Twibot-22 RoBERTa 鏈湴鎺ㄦ柇 | HuggingFace transformers锛孋PU 鍙嬪ソ | research锛堜腑鏂?zero-shot 鎬ц兘鏈煡锛?| 鏈紑濮?| 鍚屼笂 |
| 瑙勫垯缁熻鐗瑰緛锛?0-15 涓級 | 鍙戞枃闂撮殧CV / 浣滄伅瑙勫緥 / 璺ㄥ钩鍙伴噸璐?/ 澶村儚缂哄け绛?| research锛堢壒寰佹竻鍗曞緟璁鸿瘉锛?| 閮ㄥ垎宸插湪 `automation_score` | `core/account/bot_detector.py` |
| 涓夎矾闄嶇骇 + Fusion | API 鈫?妯″瀷 鈫?瑙勫垯锛沠inal=0.4路rule+0.6路ml | engineering | 鏈紑濮?| 鍚屼笂 |

### 5bis.2 鍏朵粬鎶€鏈敮鎸?
| 瀛愰」 | 绠€杩?| 鏍囩 | 褰撳墠鐘舵€?| 钀界偣 |
|---|---|---|---|---|
| 璐﹀彿绾?stance 鑱氬悎 | 鍔犳潈棰戠巼 + 鏋佸寲鎸囨暟 + 涓€鑷存€?| 杈圭晫锛堝叕寮?research + 瀹炵幇 engineering锛?| 鉂?闃诲浜?Propagation Analysis WP4 | `core/account/stance_aggregator.py`锛堝緟鏂板锛?|
| KOL 璇嗗埆 | 瑙勫垯鍖栧垎绾э紙head/mid/tail锛?+ 閰嶇疆闃堝€?| engineering | 鏈紑濮?| `core/account/kol_identifier.py`锛堝緟鏂板锛?|
| 琛屼负鐢诲儚锛堟棫锛?| 鍙戞枃棰戠巼/浣滄伅/鍐呭澶氭牱鎬?| engineering | 鉁?MVP 宸插疄鐜?| `core/account_profiler.py` (185)锛屽緟杩佸叆鏂板寘 |
| 鑷姩鍖栧€惧悜璇勫垎锛堟棫锛?| 澶氱淮 0-100 缁煎悎璇勫垎 | engineering | 鉁?MVP 宸插疄鐜?| 鍚屼笂 |
| **鍗曠敤鎴蜂富椤甸噰闆嗭紙F-ACCT-6锛?* | 璋冪敤 MediaCrawler creator 妯″紡鎶撲富椤靛厓鏁版嵁 + 鍏ㄩ儴鍙戞枃 | engineering | 鏈紑濮?| `core/account/homepage_collector.py` + `core/crawler/social.py` 鎵╁睍 `mode=creator` |
| **鍐呭宸℃锛團-ACCT-6锛?* | 瀵硅处鍙峰叏閮ㄥ彂鏂囧仛椋庨櫓/绔嬪満/妯℃澘鍖栨娴嬶紝**鍏ㄩ儴澶嶇敤涓婃父绠楁硶** | engineering锛堢紪鎺掞級 | 鉂?闃诲浜?Propagation Analysis WP4/5 + F-COORD 閫氶亾 | `core/account/content_checker.py` |
| 璐﹀彿鐢诲儚 API | `GET /accounts/profile/{id}` + 4 涓瓙绔偣 + F-ACCT-6 涓変釜鏂扮鐐?| engineering | 闆忓舰 | `api/v1/accounts.py` (30) |
| 鏈嶅姟灞?| 鑱氬悎鎵€鏈夊瓙妯″潡 + 缂撳瓨 + 缂栨帓涓婚〉閲囬泦 | engineering | 闆忓舰 | `services/account_service.py` (43, 寰呮墿) |
| 缂撳瓨灞?| Redis + TTL锛坆ot 7d / stance 6h / kol 30d锛?| engineering | 鏈紑濮?| `account_service.py` 鍐?|
| 鍓嶇璐﹀彿鐢诲儚椤?| 璇勫垎 + 鎺掑簭 + bot / stance / KOL 涓夋 | engineering | 鍩虹椤靛凡鏈?| `frontend/views/accounts/` |
| **鍓嶇璐︽埛璇︽儏椤碉紙F-ACCT-6锛?* | 涓婚〉鍏冩暟鎹?+ 鍐呭娴?+ 宸℃缁撴灉涓夋爮 | engineering | 鏈紑濮?| `frontend/views/accounts/detail/index.vue` |

璇﹁ [F-ACCT-account-profiling.md](./F-ACCT-account-profiling.md)銆?
---

## 鍏€佸叏绯荤粺鍏辩敤 engineering锛堜笉灞炰簬鍗曚竴鍔熻兘锛?
| 妯″潡 | 瀛愰」 | 褰撳墠鐘舵€?| 浼樺厛绾?|
|---|---|---|---|
| 鏁版嵁閲囬泦 | Mock + 鐪熷疄鐖櫕锛圡ediaCrawler/NewsCrawler 灏佽锛?| 鉁?MVP | 鈥?|
| 鏁版嵁鏍囧噯鍖?| DataNormalizer 璺ㄥ钩鍙板瓧娈?| 鉁?瀹屾垚 | 鈥?|
| 鏁版嵁搴?| MySQL + MongoDB + Redis 閮ㄧ讲 | 鉁?docker-compose | 鈥?|
| 鐢ㄦ埛璁よ瘉 | JWT + 瑙掕壊鏉冮檺锛坅dmin/analyst/viewer锛?| 鉁?瀹屾垚 | 鈥?|
| **鐩戞祴鐪嬫澘** | 绯荤粺姒傝/鐑偣鎺掕/骞冲彴缁熻/椋庨櫓瓒嬪娍鍥?| 馃敳 寰呭紑鍙戯紙`dashboard/index.vue` 鍗犱綅锛?| P1 |
| **棰勮绠＄悊** | 浜嬩欢绾?缇や綋绾?claim 绾у憡璀?| 馃敳 寰呭紑鍙?| P2 |
| **鎶ュ憡涓績** | 鎶ュ憡鍒楄〃/PDF 瀵煎嚭/妗堜緥褰掓。 | 馃敳 寰呭紑鍙?| P2 |
| **绯荤粺閮ㄧ讲** | Dockerfile + 鍏ㄦ爤 Compose 涓€閿儴缃?| 馃敳 寰呭紑鍙?| P2 |

---

## 涓冦€乺esearch 浠诲姟娓呭崟锛堟湰鍦板疄楠岋級

鎸夋墍灞炲姛鑳戒笌浼樺厛绾ф帓鍒楋細

| 浼樺厛绾?| 鍔熻兘 | 浠诲姟 | 褰撳墠闃诲 | 楠岃瘉鏂瑰紡 |
|---|---|---|---|---|
| P0 | F-PROP | CascadeSwitch W/b/蟿 鍙傛暟鏍″噯 | 鍙傛暟涓洪粯璁ゅ€?| 鍦?DeepHawkes Weibo / CasFlow Twitter 涓婂姣?ARIMA/Prophet 鍩虹嚎 |
| P0 | F-PROP | LLM event prompt 宸ョ▼ | prompt 鏈湪鐪熷疄鏍锋湰杩唬 | 100 鏉℃爣娉ㄦ牱鏈笂鐨勪簨浠剁被鍨嬪垎绫诲噯纭巼 |
| P1 | F-COORD | PSL 瀵圭О瓒呭嚑浣?+ Cauchy + BH-FDR | 浠ｇ爜鏈紑濮?| 5 娑堣瀺鍙樹綋 + Seckin 2024 IO 鏍囨敞鏁版嵁闆?FDR 鏍″噯 |
| P1 | F-COORD | 璇箟閫氶亾锛圫emanticPairAdapter锛?| 妯″瀷閫夋嫨 + kNN 姹犲ぇ灏?| 鍦?mock 鏁版嵁涓婇獙璇?p_sem 鐨勯浂鍒嗗竷杩戜技 |
| P1 | F-RISK | Phase-Aware Hazard 5 鍙傛暟 | 鍙傛暟鏈牎鍑?| 鍘嗗彶鎴樺焦 case study + 杞崲鍑嗙‘鐜?|
| P1 | F-RISK | D-S 铻嶅悎 9+5 鍙傛暟 | 杈圭晫 case 鏈祴璇?| mass=0 / mass=1 / 鍐茬獊璐ㄩ噺鏋侀珮 涓夌杈圭晫 |
| P2 | F-COORD | 绾ц仈閫氶亾锛圕ascade Channel锛?| 瀛愮被鍨嬬粺璁℃€ц川鏈獙璇?| 璇勮閾捐秴鍑犱綍妫€楠屽悎鐞嗘€?|
| P2 | F-PROP | 绔嬪満妫€娴?+ 鍗卞璇勪及锛?*甯栫骇**锛孭ropagationAnalysis WP4-5锛?| 鏍囩浣撶郴鏈畾 | 鍏堜笌瀵煎笀/绔炶禌鎸囧纭畾 6 绫荤珛鍦?+ 鍗卞缁村害 |
| P2 | F-RISK | DISARM 18 鏉¤矾寰勮浆鎹㈡鐜?| 褰撳墠涓洪鍩熷厛楠?| 瀹炴垬 case 杩唬 |
| P2 | F-ACCT | Bot detection 棰勮缁冩ā鍨嬮€夋嫨锛圧1锛?| 涓枃 zero-shot 鎬ц兘鏈煡 | 100 鏉℃爣娉ㄥ井鍗氳处鍙蜂笂瀵规瘮 Botometer / Twibot-22 / 瑙勫垯 |
| P2 | F-ACCT | 瑙勫垯鐗瑰緛娓呭崟璁鸿瘉锛圧3锛?| 10-15 涓壒寰佹湭瀹?| 涓庣幇鏈?`automation_score` 鐗瑰緛瀵规瘮 + 鏂囩尞缁艰堪 |
| P2 | F-ACCT | 璐﹀彿绾?stance 鑱氬悎鍏紡锛圧4锛?| 鍔犳潈 vs 绠€鍗曢鐜?/ 鏋佸寲瀹氫箟 | 鏍囨敞璐﹀彿涓婁汉宸ヨ瘎浼?6 缁村垎甯?|
| P2 | F-ACCT | KOL 闃堝€煎钩鍙版牎鍑嗭紙R5锛?| 璺ㄥ钩鍙伴槇鍊煎樊寮?| weibo/douyin/xhs 鍚?50 涓爣娉ㄨ处鍙?|

**鏈湴瀹為獙鎵ц绾﹀畾**锛?
- 姣忎釜 research 浠诲姟鍦ㄦ湰鍦板垎鏀?`aris/t{1,2,3}-experiment-{name}` 涓嬭繘琛?- 瀹為獙浜х墿锛坄outputs/`銆乣logs/`锛変笉鍏?git锛岀粨璁哄洖鍐欏埌瀵瑰簲 `aris/tech-NN/REQUIREMENTS.md`
- GPU 浠诲姟鍙敤 vast.ai / Modal / 鍚櫤骞冲彴锛堝弬瑙?`qzcli` skill锛?
---

## 鍏€乪ngineering 浠诲姟娓呭崟锛圕laude Code 蹇€熷畬鎴愶級

鎸変紭鍏堢骇鎺掑垪锛屾瘡鏉″甫宸ヤ綔閲忛浼帮細

| 浼樺厛绾?| 鍔熻兘 | 浠诲姟 | 宸ヤ綔閲?| 楠岃瘉 |
|---|---|---|---|---|
| P0 | F-RISK | 琛?`alembic` 杩佺Щ浠ユ敮鎸?`risk_assessment` 琛?| 30 min | `alembic upgrade head` 涓嶆姤閿?|
| P0 | F-PROP/F-RISK | 琛?`pyproject.toml` LLM 瀹㈡埛绔緷璧栵紙openai/dashscope锛?| 30 min | `uv sync` 閫氳繃 |
| P0 | F-PROP/F-RISK | 瀹炵幇 `llm_client.py`锛堝紓姝?+ 閲嶈瘯 + mock fallback锛夛紝鏇挎崲 `llm_bridge.py` stub | 2 h | mock 妯″紡涓嬪畬鏁磋皟鐢ㄩ€氳繃 |
| P0 | 娌荤悊 | git 娌荤悊鎬ф彁浜わ紙aris/doc/memory/AGENTS.md/CLAUDE.md锛?| 30 min | `git status` 娓呮磥 |
| P1 | F-COORD | `channels.py` 澶氶€氶亾 Object 鎻愬彇锛堣鍒欏寲锛屼笉娑夌畻娉曪級 | 3-4 h | 鍗曞厓娴嬭瘯瑕嗙洊 4 绉?channel |
| P1 | F-COORD | `coordination_service.py` 鎵╁睍浠ヤ覆閫氭柊閫氶亾 | 2 h | API 鑱旇皟閫氳繃 |
| P1 | F-PROP | `cascade_events.py` 绾ц仈褰㈡€佷簨浠舵娴嬶紙瑙勫垯鍖栭檷绾э級 | 3 h | 鍦?mock 鏁版嵁涓婅緭鍑?6 绫讳簨浠?|
| P1 | F-PROP | `propagation_service.py` 鎵╁睍浠ヤ覆閫?WP1-3 | 2 h | API 鑱旇皟閫氳繃 |
| P1 | F-RISK | 鍓嶇 DISARM 璺緞鍙鍖栵紙ECharts force-directed锛?| 4-6 h | 18 鏉¤竟娓叉煋姝ｇ‘ |
| P0 | F-ACCT | 鐩綍杩佺Щ锛歚core/account_profiler.py` 鈫?`core/account/activity_profiler.py` + shim | 1 h | 鏃?import 璺緞涓嶇牬鍧?|
| P0 | F-ACCT | 琛?`pyproject.toml`锛坱ransformers/torch CPU锛? `.env` 鐜鍙橀噺 | 30 min | `uv sync` 閫氳繃 |
| P0 | F-ACCT | alembic 杩佺Щ `account_profile_cache` 琛?| 30 min | `alembic upgrade head` 涓嶆姤閿?|
| P1 | F-ACCT | `bot_detector.py` 鍙屽眰 + 3 璺檷绾?+ mock锛堣鍒欒矾寰勫厛琛岋級 | 5-7 h | API/妯″瀷/瑙勫垯涓夎矾鍧囧彲瑙﹀彂 |
| P1 | F-ACCT | `kol_identifier.py` 瑙勫垯鍖?+ 閰嶇疆鍔犺浇 | 2-3 h | 涓夌 KOL tier 鏍囨敞姝ｇ‘ |
| P1 | F-ACCT | `account_service.py` 鎵╁睍 4 涓柊鏂规硶 | 2 h | 鏈嶅姟灞傝仈璋冮€氳繃 |
| P1 | F-ACCT | `api/v1/accounts.py` 鏂板 4 涓鐐?| 2 h | API 鑱旇皟閫氳繃 |
| P1 | F-ACCT | 鍓嶇 3 涓?Panel 缁勪欢锛圔ot/Stance/KOL锛?+ 璺敱 | 5-6 h | 涓夋灞曠ず姝ｇ‘ |
| P2 | F-ACCT | `stance_aggregator.py`锛堜緷璧?F-PROP WP4 瀹屾垚锛?| 2-3 h | 涓?F-PROP 鎺ュ彛鑱旇皟 |
| P2 | F-ACCT | Redis 缂撳瓨灞?+ TTL 绛栫暐 | 2 h | 鍛戒腑鐜囩洃鎺?|
| P1 | F-ACCT | F-ACCT-6 涓婚〉閲囬泦锛歚homepage_collector.py` + `social.py` 鎵╁睍 `mode=creator` | 6-8 h | weibo/douyin/xhs 涓夊钩鍙颁富椤靛彲鎷夊彇 |
| P1 | F-ACCT | F-ACCT-6 鍐呭宸℃锛歚content_checker.py` 缂栨帓锛堜笂娓哥己澶辨椂 mock fallback锛?| 3-4 h | 鍗曡处鍙疯鏂欐壒澶勭悊 |
| P1 | F-ACCT | F-ACCT-6 alembic 杩佺Щ `account_homepage` 琛?+ ORM | 1 h | `alembic upgrade head` |
| P1 | F-ACCT | F-ACCT-6 API 3 绔偣 + 鍓嶇璐︽埛璇︽儏椤碉紙涓婚〉 + 鍐呭娴?+ 宸℃涓夋爮锛?| 8-10 h | E2E 娓叉煋姝ｇ‘ |
| P2 | 鍏ㄥ眬 | 鐩戞祴鐪嬫澘锛堢郴缁熸瑙?+ 鐑偣鎺掕 + 椋庨櫓瓒嬪娍锛?| 1-2 d | 鎺ュ叆鍚庣缁熻 API |
| P2 | 鍏ㄥ眬 | 鎶ュ憡涓績锛堝垪琛?+ PDF 瀵煎嚭 + 妗堜緥褰掓。锛?| 1-2 d | 绔埌绔敓鎴愭姤鍛?|
| P2 | 鍏ㄥ眬 | 棰勮绠＄悊锛堣鍒欓厤缃?+ 鍛婅鐘舵€侊級 | 1-2 d | 瑙﹀彂娴佺▼鑱旇皟 |

---

## 涔濄€佽法 analysis capability 渚濊禆涓庡绾?
| 涓婃父 | 涓嬫父 | 鏁版嵁 | 濂戠害鏂囦欢 | 鐜扮姸 |
|---|---|---|---|---|
| F-COORD | F-PROP | `coord_groups` / `network_density` / `evidence_edges` | `aris/shared/CROSS_ANALYSIS_DEPS.md` | 瀛楁绾﹀畾瀹屾垚锛屾帴鍙ｆ湭鑱旇皟 |
| F-PROP | F-RISK | `trend / stance / harm / source / scope` | 鍚屼笂 | Review 宸茬敤鍗犱綅鏁版嵁锛岀瓑 Propagation Analysis WP4-5 瀹屾垚鍚庢浛鎹?|
| F-RISK | UI | `risk_assessment_report.json` 缁撴瀯鍖?| `aris/tech-03-risk/ACCEPTANCE.md` | 瀛楁绾﹀畾瀹屾垚锛屽墠绔矾寰勫浘寰呰ˉ |
| F-ACCT | F-COORD | `bot_score` / `is_kol` 鐢ㄤ簬杩囨护 / 鍔犳潈 | F-ACCT 鏂囨。 搂8.1 | 瀛楁绾﹀畾瀹屾垚锛屽緟 F-ACCT MVP 涓婄嚎 |
| F-ACCT | F-PROP | 璐﹀彿鐢诲儚锛圞OL 鏍囪瘑 / 鑷姩鍖栧€惧悜锛変綔涓轰簨浠惰瘎鍒?e 鐨勮緭鍏?| F-ACCT 鏂囨。 搂8.2 | 鍚屼笂 |
| F-ACCT | F-RISK | group `bot_ratio` / KOL 鍒嗗竷浣滀负 mass(manipulation) 杈撳叆 | F-ACCT 鏂囨。 搂8.3 | 鍚屼笂 |
| F-PROP WP4 | F-ACCT | **甯栫骇** stance 鈫?F-ACCT 鑱氬悎涓?*璐﹀彿绾?* stance | F-ACCT 鏂囨。 搂8.4 | 鈿狅笍 闃诲 F-ACCT-2锛岄渶 F-PROP 鏆撮湶 `/propagation/stance/by-account` |
| Propagation Analysis WP4/WP5 | F-ACCT-6 | 甯栫骇绔嬪満 + 甯栫骇鍗卞璇勫垎浣滀负鍐呭宸℃鐨勫瓧娈佃緭鍏?| F-ACCT 鏂囨。 搂8.5 | 鈿狅笍 闃诲 content_checker 鐪熷疄杈撳嚭锛涗笂娓哥己澶辨椂 mock fallback |
| F-COORD channels.py | F-ACCT-6 | 鍗曡处鍙疯鏂欐ā鏉垮寲妫€娴嬶紙璇箟閲嶅 / hashtag 妯℃澘锛?| F-ACCT 鏂囨。 搂8.5 | 鈿狅笍 闃诲 template_detector 瀛愭帴鍙ｏ紱涓婃父缂哄け鏃惰繑鍥?null |
| MediaCrawler creator 妯″紡 | F-ACCT-6 | 涓婚〉鍏冩暟鎹?+ 鍏ㄩ噺鍙戞枃娴侀噰闆?| `core/crawler/social.py` 鎵╁睍 `mode=creator` | weibo / douyin / xhs 宸叉敮鎸侊紝闇€ social.py 鎺ュ叆 |

---

## 鍗併€佹帹鑽愭墽琛岃妭濂?
**绗竴鍛紙engineering锛孋laude Code 涓诲锛?*锛?
1. Day 1锛歅0 鍏ㄩ儴瀹屾垚锛坅lembic + LLM 渚濊禆 + `llm_client.py` + git 娌荤悊锛?2. Day 2-3锛欶-COORD P1锛坄channels.py` + 鏈嶅姟灞傛墿灞曪級
3. Day 4锛欶-PROP P1锛坄cascade_events.py` + 鏈嶅姟灞傛墿灞曪級
4. Day 5锛欶-RISK P1锛圖ISARM 璺緞鍓嶇鍙鍖栵級

**绗簩鍛紙research锛屾湰鍦板疄楠岋級**锛?
1. F-PROP P0锛欳ascadeSwitch 鍙傛暟鏍″噯 + LLM event prompt 杩唬
2. F-COORD P1锛歅SL 绠楁硶瀹炵幇 + 娑堣瀺瀹為獙
3. F-RISK P1锛歅hase-Aware Hazard 鍙傛暟鏍″噯

**绗笁鍛紙璺?analysis capability 鑱旇皟 + 鍏ㄥ眬 engineering P2锛?*锛?
1. F-COORD 鈫?F-PROP 鈫?F-RISK 鎺ュ彛鑱旇皟
2. 鐩戞祴鐪嬫澘 / 鎶ュ憡涓績 / 棰勮绠＄悊

---

## 鍗佷竴銆佸紩鐢?
- 鍥涗唤鍔熻兘绾ч渶姹傛枃妗ｏ細
  - [aris/tech-01-coordination/REQUIREMENTS.md](../../aris/tech-01-coordination/REQUIREMENTS.md)锛團-COORD锛?  - [aris/tech-02-propagation/REQUIREMENTS.md](../../aris/tech-02-propagation/REQUIREMENTS.md)锛團-PROP锛?  - [aris/tech-03-risk/REQUIREMENTS.md](../../aris/tech-03-risk/REQUIREMENTS.md)锛團-RISK锛?  - [F-ACCT-account-profiling.md](./F-ACCT-account-profiling.md)锛團-ACCT 妯悜鏀拺锛?- 宸ョ▼涓荤嚎鏂囨。锛?  - [development-roadmap.md](./development-roadmap.md)
  - [development-log.md](./development-log.md)
- analysis capability 鐮旂┒鑳屾櫙锛?  - [doc/research/key-technology-background/](../research/key-technology-background/)
- 璁板繂浣擄紙Session Startup锛夛細
  - [memory/PLAYBOOK.md](../../memory/PLAYBOOK.md)
  - [memory/state_coordination_discover.md](../../memory/state_coordination_discover.md) / [state_propagation_analysis.md](../../memory/state_propagation_analysis.md) / [state_review.md](../../memory/state_review.md)

