# 鍏抽敭鎶€鏈笁锛氬崗鍚屾敾鍑荤殑鎶ュ憡鐮斿垽锛圥hase-Aware Hazard + DISARM 璺緞棰勫垽 + 澶?Agent 缂栨帓锛?
> **鐢ㄩ€?*锛氬畾涔?Review 鐨勭爺绌堕棶棰樸€佸綋鍓嶅伐绋嬭惤鐐广€佺爺绌剁洰鏍囥€佸疄鐜版柟鍚戝拰楠岃瘉鏂瑰紡銆? 
> **鍙椾紬**锛歊eview 鐮旂┒瀹炵幇鑰呫€佹姤鍛婄爺鍒?DISARM 妯″潡缁存姢鑰呫€? 
> **缁存姢瑙勫垯**锛氬彧鍐欏叧閿妧鏈儗鏅笌鐮旂┒鏂规锛涗骇鍝佹帴鍙ｅ拰浠诲姟鐘舵€佹斁鍏?`../../engineering/`銆?
> 鏂瑰悜鏇存柊锛?026-06-02锛夛細Review 瀹氫綅涓洪棴鐜湯绔殑鈥滄姤鍛婄爺鍒も€濓紝鍒嗕笁娈碉細**(a) 鍩轰簬 Agent 鐨勮瘉鎹紪鎺掞紙鍚敤鎴疯█璁?琛屼负妫€娴嬶級鈫?(b) 鍩轰簬 RAG 鐨勬姤鍛婄敓鎴?鈫?(c) Agent 瀵瑰崗鍚屾敾鍑荤殑瑙ｉ噴鎬荤粨**銆?> 閲嶈琛ㄨ堪绾緥锛氶拡瀵硅瘎瀹♀€滅敤 Agent 鍋氭姤鍛婄爺鍒ゅ垱鏂版€ц緝寮扁€濈殑鎰忚锛?*澶村彿鍒涙柊蹇呴』鏄凡钀藉湴鐨勭櫧鐩掑墠鐬诲紩鎿?*锛圥hase-Aware Hazard 闃舵棰勮 + DISARM 鏀诲嚮璺緞棰勫垽涓庡弽鍒?+ 闃舵璋冨埗 D-S 铻嶅悎锛夛紝Agent / RAG 浠呬綔涓虹紪鎺掑熀搴т笌鍛堢幇灞傦紝**涓嶄綔涓哄垱鏂板崠鐐?*銆傛牳蹇冨彊浜嬶細浠?detection 鍗囩骇鍒?anticipation + countermeasure锛堥娴嬩笅涓€姝ユ敾鍑绘妧鏈?+ 缁欏嚭鍙嶅埗锛夈€?
## 1. 闂瀹氫箟

鎶ュ憡鐮斿垽鎶婁笂娓稿崗鍚屽彂鐜帮紙Coordination Discover锛変笌浼犳挱鐩戞帶锛圥ropagationAnalysis锛夌殑缁撴灉缁勭粐鎴愮粺涓€璇佹嵁閾撅紝瀵逛簨浠?/ claim / thread 灞傜骇杈撳嚭鍙璁＄殑鐮斿垽涓庡缃缓璁紝鍥炵瓟涓変釜闂锛?
- **褰撳墠椋庨櫓澶氶珮**锛堜俊蹇靛尯闂?+ 鍐茬獊妫€娴嬶紝闈炵偣浼拌锛?- **鎺ヤ笅鏉ヤ細鍙戠敓浠€涔?*锛堥樁娈佃浆鎹?breakout 棰勬祴 + DISARM 涓嬩竴姝ユ妧鏈娴嬶級
- **搴旇濡備綍搴斿**锛堝熀浜庨娴嬫敾鍑昏矾寰勭殑鍙嶅埗寤鸿锛?
鍐呭灞傚垎鏋愶紙绔嬪満妫€娴嬨€佸嵄瀹?鏈夊瑷€璁鸿瘎浼帮級鎸夐棴鐜垎宸ョ粺涓€褰?Review 鐨?Characterization 灞傘€?
## 2. 褰撳墠浠ｇ爜鍩虹嚎

`core/review/` 宸茶惤鍦帮紙绾?1340 琛岋紝CPU 鐧界洅锛屽凡鐢?`risk_service.py` 璺戦€氾級锛?
- `system/backend/app/core/review/evidence_builder.py`锛氬婧愯瘉鎹寘鏋勫缓
- `system/backend/app/core/review/phase_detector.py`锛? 鐘舵€佹垬褰圭敓鍛藉懆鏈?+ logistic hazard 闃舵杞崲/breakout 棰勬祴
- `system/backend/app/core/review/disarm_scorer.py`锛欴ISARM 鎶€鏈浆鎹㈠浘 + 鏀诲嚮璺緞璇勫垎 + 涓嬩竴姝ユ妧鏈娴?+ 鍙嶅埗寤鸿
- `system/backend/app/core/review/ds_fusion.py`锛欴empster-Shafer 铻嶅悎 + phase-conditioned 璐ㄩ噺璋冨埗 + 鍐茬獊妫€娴?- `system/backend/app/core/review/report_builder.py`锛氱粨鏋勫寲鎶ュ憡鐢熸垚
- `system/backend/app/core/review/llm_bridge.py`锛?*浠呯害 30 琛屽崰浣?*锛堝緟鍗囩骇涓?DeepSeek Agent 缂栨帓鍣級
- `system/backend/app/services/risk_service.py`銆乣api/v1/risk.py`銆佸墠绔?`views/risk/index.vue`

鏈惤鍦帮紙璁捐绋匡級锛歀ayer 2 RAG 鎶ュ憡鐢熸垚銆丩ayer 3 鎭舵剰瑷€璁?绔嬪満/鍙嶅埗鍙欎簨 Agent锛屼互鍙?Agent 缂栨帓鍣ㄦ湰浣擄紙`agent`/`rag`/`retriever` 绛夋枃浠朵笉瀛樺湪锛夈€?
## 3. 涓夊眰鏋舵瀯锛圓gent 缂栨帓鐗堬級

- **Layer 1 妫€娴嬬爺鍒わ紙宸茶惤鍦帮紝浣滀负 Agent 鐨?tools锛?*锛歅hase Agent锛坧hase_detector锛? Evidence Agent锛坉s_fusion锛? DISARM Agent锛坉isarm_scorer锛?- **Layer 2 RAG + Agent 鎶ュ憡鐢熸垚锛堣璁＄锛?*锛氭绱㈠巻鍙叉姤鍛婂簱 + DISARM 鐭ヨ瘑搴?+ 浜嬩欢璇佹嵁 鈫?DeepSeek 鐢熸垚缁撴瀯鍖栨姤鍛?- **Layer 3 鍙嶉涓庢墿灞曟娴嬶紙璁捐绋匡級**锛氭伓鎰忚█璁?/ 绔嬪満 / 鍙嶅埗鍙欎簨 Agent
- LLM 鍚庣锛欴eepSeek API锛汚gent 涓嶅仛鏈€缁堣鍐筹紝鏍稿績妫€娴嬭蛋宸茶惤鍦扮殑缁熻/瑙勫垯/鍥捐矾绾?
## 4. 杩欎竴鎶€鏈嚎瑕佽В鍐崇殑鏍稿績闂

- 濡備綍鎶婂崗鍚屻€佷紶鎾€佽处鎴风粨鏋滄敹鏉熷埌缁熶竴璇佹嵁鍖呭苟鍋氶樁娈垫劅鐭ョ爺鍒?- 濡備綍鎶?DISARM 浠庘€滄爣绛炬槧灏勨€濇彁鍗囦负鈥滄敾鍑昏矾寰勬帹鐞?+ 涓嬩竴姝ラ娴?+ 鍙嶅埗鈥?- 濡備綍璁?LLM/Agent 鍙妸鐧界洅缁撴瀯鍖栫粨璁衡€滅炕璇戞垚浜鸿瘽鈥濓紝涓ョ鏀瑰垎/涓嬬粨璁猴紝淇濊瘉鍙璁?- 濡備綍杈撳嚭鑳借鐪嬫澘銆佹姤鍛娿€侀璀﹀鐢ㄧ殑 JSON 缁撴瀯

## 5. 鎺ㄨ崘瀹炵幇鏂瑰悜涓庤〃杩扮邯寰?
- 澶村彿鍒涙柊璁?Layer 1 宸茶惤鍦扮殑鐧界洅绠楁硶锛坔azard 棰勮 + DISARM 璺緞棰勫垽 + 鍙嶅埗 + 闃舵璋冨埗 D-S锛夛紝CPU-only銆佸彲瀹¤
- DISARM鈥滈娴嬩笅涓€姝ユ妧鏈€濊寖寮忔簮鑷綉缁滃畨鍏?ATT&CK 鍩燂紙MITRE TIE 绛夛級锛屾湰璐＄尞瀹氫綅涓?*璺ㄥ煙杩佺Щ鍒?DISARM 淇℃伅鎿嶇旱鍩?+ 闃舵鏉′欢鍖?*锛屼笉瀹滅О棣栧垱
- Agent / RAG 鏄紪鎺掍笌鍛堢幇灞傦紝閬垮厤涓绘墦鈥滃 Agent + RAG 鎶ュ憡鐢熸垚鈥濓紙绾㈡捣锛屽凡琚?arXiv 2505.17511銆?601.15109 绛夊崰浣嶏級
- `llm_bridge.py` 鍗囩骇鏃朵弗鏍奸檺瀹氳緭鍏ヤ负 Layer 1 宸茬畻鍑虹殑缁撴瀯鍖栫粨鏋?
## 6. 鎺ㄨ崘楠岃瘉鏂瑰紡

- 閽堝绾悗绔湇鍔¤ˉ鍗曞厓娴嬭瘯涓庡搷搴旂粨鏋勬祴璇?- 閫夊彇 `mock_weibo` / `weibo` / `news` 灏忔牱渚嬮獙璇?JSON 鎶ュ憡绋冲畾鎬?- 楠岃瘉閲嶇偣鏄€滈娴嬫湁鐢ㄦ€р€濓紙breakout 鍓嶈兘鍚﹂璀︺€佷笅涓€姝ユ妧鏈娴嬫槸鍚︿紭浜庡惎鍙戝紡銆佸弽鍒舵槸鍚﹀彲鎿嶄綔锛夛紝鑰岄潪鍒嗙被瀹岀編鎬?
## 7. 鍙傝€冩枃鐚嚎绱?
- `Phase-Aware / campaign lifecycle` 涓?early-warning锛坔azard / breakout 棰勬祴锛?- MITRE ATT&CK 鏀诲嚮閾?鎶€鏈浆鎹㈤娴嬶紙TIE銆丮arkov attack-chain锛岃縼绉绘潵婧愶級
- Agentic DISARM for FIMI (arXiv 2601.15109, 2026) 鈥?flat tagging 瀵圭収锛孯eview 宸紓鍦?path reasoning + 棰勬祴 + 鍙嶅埗
- Multi-agent Misinformation Lifecycle (arXiv 2505.17511, 2025) 鈥?澶?agent 鍏ㄧ敓鍛藉懆鏈熷鐓?- `DISARM Red Framework`

