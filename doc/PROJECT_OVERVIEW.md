# CogGuard 椤圭洰瀹屾暣璁捐鏂囨。锛氬姛鑳借璁′笌鎶€鏈€夊瀷

> 鐗堟湰锛?026-06-03 锝?鍩虹嚎锛歚release-0.2` 锝?浜у搧浠ｇ爜鏍癸細`system/`
> 鐢ㄩ€旓細缁撻绛旇京 / 椤圭洰浜や粯鐢ㄧ殑鍗曟枃浠舵€昏锛岃鐩栫郴缁熷畾浣嶃€侀棴鐜€佷笁澶у叧閿妧鏈殑鍔熻兘璁捐涓庢妧鏈€夊瀷銆佺湡瀹炶惤鍦扮姸鎬佷笌宸窛銆?> 缁存姢瑙勫垯锛氭湰鏂囧尯鍒?*宸茶惤鍦帮紙浠ｇ爜鍙繍琛岋級**銆?*璁捐绋匡紙浠呮枃妗?鏂规锛?*銆?*缂哄彛锛堟棤璁捐鏃犱唬鐮侊級**涓夋€侊紝涓嶆妸璁″垝褰撳畬鎴愩€?
---

## 0. 涓€椤甸€熻

| 缁村害 | 鍐呭 |
|------|------|
| 椤圭洰瀹氫綅 | 闈㈠悜缃戠粶鑸嗚瀵规姉鐨?*璺ㄥ钩鍙板崗鍚屾搷绾靛垎鏋?*璇佹嵁椹卞姩鍘熷瀷绯荤粺 |
| 鏍稿績闂幆 | 浜嬩欢 鈫?璇佹嵁 鈫?**鍗忓悓鍙戠幇(Coordination Discover)** 鈫?**浼犳挱鐩戞帶(Propagation Analysis)** 鈫?**鎶ュ憡鐮斿垽(Risk Review)** 鈫?澶勭疆 |
| 楠岃瘉鑼冨洿 | `mock_weibo`銆乣weibo`銆乣news`锛堣法婧愶紝闈炶法骞冲彴韬唤瑙ｆ瀽锛?|
| 鍚庣 | Python 3.11 / FastAPI / SQLAlchemy(async) / Motor / Celery |
| 鍓嶇 | Vue 3 / TypeScript / Vite 6 / Ant Design Vue 4 / ECharts 6 / Pinia |
| 瀛樺偍 | MySQL 8锛堢粨鏋勫寲锛? MongoDB 7锛堝師濮嬫暟鎹級/ Redis 7锛堢紦瀛?闃熷垪锛?|
| 鍏抽敭鎶€鏈?| Coordination Discover 璺ㄥ钩鍙板叡鍚岃涓虹壒寰佸鐢ㄨ瀺鍚堟娴?锝?Propagation Analysis LLM+鏃跺簭鐨勪簨浠惰妯￠娴?锝?Risk Review Phase-Aware Hazard + DISARM 璺緞棰勫垽锛堝 Agent 缂栨帓锛?|

**涓€鍙ヨ瘽鐜扮姸**锛氭暟鎹噰闆嗐€佸崗鍚屾娴?MVP銆佷紶鎾秼鍔块娴嬫牳蹇冦€佹姤鍛婄爺鍒ょ櫧鐩掑紩鎿庡潎宸茶惤鍦板彲杩愯锛涗笁澶у叧閿妧鏈悇鑷殑"鍒涙柊澧炲己灞?锛圞T1 鐨?PSL銆並T2 鐨勭湡瀹?LLM 鎺ュ叆涓庤矾寰勯娴嬨€並T3 鐨?Agent/RAG 灞傦級澶氫负璁捐绋匡紝涓斿瓨鍦?LLM 瀹㈡埛绔緷璧栫己澶辫繖涓€鍏辨€ч樆濉炪€?
---

## 1. 绯荤粺瀹氫綅涓庝富绾垮彊浜?
CogGuard 鍥寸粫"璺ㄥ钩鍙板崗鍚屾敾鍑?寤虹珛涓€鏉?*鍙В閲娿€佸彲澶嶆牳**鐨勫垎鏋愰摼璺細

```
浜嬩欢 鈹€鈹€鈫?璇佹嵁 鈹€鈹€鈫?鍗忓悓鍙戠幇 鈹€鈹€鈫?浼犳挱鐩戞帶 鈹€鈹€鈫?鎶ュ憡鐮斿垽 鈹€鈹€鈫?澶勭疆
  鈹?                                                         鈹?  鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€ 澶勭疆/鍥炴祦 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?```

- **鍔熻兘涓€ 路 鍗忓悓鍙戠幇锛圞T1锛屾牳蹇冨叧閿妧鏈級**锛氱敤骞冲彴鏃犲叧鐨勫叡鍚岃涓虹壒寰佸彂鐜板崗鍚岀兢浣?- **鍔熻兘浜?路 浼犳挱鐩戞帶锛圞T2锛?*锛氶娴嬩簨浠惰妯′笌浼犳挱鎬佸娍
- **鍔熻兘涓?路 鎶ュ憡鐮斿垽锛圞T3锛?*锛氭秷璐逛笂娓歌瘉鎹紝鍋氶樁娈甸璀?+ 鏀诲嚮璺緞棰勫垽 + 鍙嶅埗 + 缁撴瀯鍖栨姤鍛?
璁捐鍘熷垯锛氳鍒?璇佹嵁浼樺厛浜庨粦鐩?LLM 瑁佸喅锛汱LM/Agent 浣滃寮轰笌鍛堢幇锛屼笉浣滅涓€闃舵鏈€缁堣鍐筹紱鍐呭鍒嗘瀽鍗曞悜涓嬫矇锛岀粷涓嶅洖娴佷綔涓哄崗鍚屽垽鎹€?
---

## 2. 鎬讳綋鏋舵瀯涓庢妧鏈€夊瀷

### 2.1 鍒嗗眰鏋舵瀯

```
鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?鈹?鍓嶇 (Vue 3 + TS + Ant Design Vue 4 + ECharts 6 + Pinia) 鈹?鈹? 鐧诲綍 / 鐩戞祴鐪嬫澘 / 鏁版嵁閲囬泦 / 鍗忓悓妫€娴?/ 浼犳挱鐩戞帶 /        鈹?鈹? 璐︽埛鐩戞祴 / 鎶ュ憡鐮斿垽                                       鈹?鈹溾攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?鈹?鍚庣 API (FastAPI, /api/v1) 鈥?7 璺敱缁?                   鈹?鈹? auth / dashboard / crawl / coordination /                鈹?鈹? accounts / propagation / risk                            鈹?鈹溾攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?鈹?鏈嶅姟灞?services/ 鈥?涓氬姟缂栨帓                                鈹?鈹溾攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?鈹?鏍稿績绠楁硶 core/ 鈥?coordination / propagation / risk /      鈹?鈹? account_profiler / crawler                               鈹?鈹溾攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?鈹?鏁版嵁灞? MySQL(鐢ㄦ埛/浠诲姟/鐮斿垽) MongoDB(甯栧瓙/璇勮/鍘熷)      鈹?鈹?        Redis(缂撳瓨+Celery broker)  NetworkX(鍐呭瓨鍥?        鈹?鈹溾攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?鈹?閲囬泦灞? MediaCrawler / NewsCrawler / MockCrawler          鈹?鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?```

### 2.2 鎶€鏈€夊瀷涓庣悊鐢?
| 灞?| 閫夊瀷 | 鐞嗙敱 |
|----|------|------|
| 鍚庣妗嗘灦 | FastAPI (Python 3.11+) | 寮傛楂樻€ц兘锛屼笌鍙傝€冮」鐩爤涓€鑷达紝鑷甫 OpenAPI |
| 鍓嶇妗嗘灦 | Vue 3 + TS + Vite 6 | 鐢熸€佹垚鐔燂紝涓?NewsCrawler 鍓嶇涓€鑷?|
| UI 缁勪欢 | Ant Design Vue 4 | 涓悗鍙版暟鎹垎鏋愬満鏅粍浠朵赴瀵?|
| 鍙鍖?| ECharts 6 | 鍗忓悓缃戠粶鍔涘鍚戙€佷紶鎾椂闂寸嚎銆佸湴鍥俱€佽秼鍔垮浘 |
| 缁撴瀯鍖栧瓨鍌?| MySQL 8 | 鐢ㄦ埛銆佷换鍔°€佺爺鍒ゆ姤鍛婄瓑缁撴瀯鍖栨暟鎹?|
| 闈炵粨鏋勫寲瀛樺偍 | MongoDB 7 (Motor 寮傛) | 甯栧瓙銆佽瘎璁恒€佺埇鍙栧師濮?JSONL |
| 缂撳瓨/闃熷垪 | Redis 7 | 缂撳瓨銆佷細璇濄€丆elery broker |
| 鍥惧垎鏋?| NetworkX锛堝唴瀛橈級 | 褰撳墠闃舵杞婚噺璺嚎锛岄鐣?Neo4j |
| 寮傛浠诲姟 | Celery + Redis | 閲囬泦銆佸垎鏋愮瓑鑰楁椂鎿嶄綔寮傛鎵ц |
| 閴存潈 | JWT (python-jose) + bcrypt (passlib) | 鏍囧噯鏂规锛岃鑹?admin/analyst/viewer |
| 鍖呯鐞?| uv锛堝悗绔級/ npm锛堝墠绔級 | 楂樻晥渚濊禆绠＄悊 |

### 2.3 鍏抽敭渚濊禆鐜扮姸锛堝凡鏍稿疄 `pyproject.toml`锛?
鍚庣**瀹為檯浠呭惈**锛歠astapi / uvicorn / sqlalchemy / aiomysql / motor / redis / celery / pydantic / python-jose / passlib / alembic / loguru / **httpx** / pandas / networkx / numpy銆?
> 鈿狅笍 **鍏辨€ч樆濉烇紙褰卞搷涓夊ぇ鍏抽敭鎶€鏈殑澧炲己灞傦級**锛?> - **鏃犱换浣?LLM 瀹㈡埛绔簱**锛堟棤 openai / dashscope / deepseek SDK锛夆€斺€擪T2 鐪熷疄浜嬩欢鎻愬彇銆並T3 Agent 鍏ㄩ潬鏈潵琛ヤ緷璧?+ httpx 鐩磋繛
> - **鏃?scipy / statsmodels** 鈥斺€?Coordination Discover 鐨?PSL锛堣秴鍑犱綍銆丅H-FDR锛夋棤娉曞疄鐜?> - **鏃?sentence-transformers / text2vec** 鈥斺€?Coordination Discover 璇箟閫氶亾鏃犳敮鎾戯紙浣嗘柊鏂瑰悜宸插喅瀹氭帓闄ゅ唴瀹逛俊鍙凤紝褰卞搷寮卞寲锛?> - **鏃?igraph / leidenalg** 鈥斺€?鑻ヨ Leiden 绀惧尯鍙戠幇闇€鏂板锛堝綋鍓嶇敤 NetworkX greedy modularity锛?
---

## 3. 鏁版嵁閲囬泦锛堥棴鐜緭鍏ワ級

璺ㄥ钩鍙版暟鎹帴鍏ヤ笌鏍囧噯鍖栵紝鏄暣鏉￠棴鐜殑杈撳叆銆?
| 瀛愭ā鍧?| 鏂囦欢 | 鐘舵€?| 璇存槑 |
|--------|------|------|------|
| 鐖櫕鎶借薄鍩虹被 | `core/crawler/base.py` | 鉁?宸茶惤鍦?| 缁熶竴鎺ュ彛 |
| Mock 鐖櫕 | `core/crawler/mock.py` | 鉁?宸茶惤鍦?| 鐢熸垚鍚崗鍚屾ā寮忕殑娴嬭瘯鏁版嵁 |
| MediaCrawler 鐩磋繛 | `core/crawler/social.py` (883琛? | 鉁?宸茶惤鍦?| 寰崥绛夌ぞ浜わ紝瀛愯繘绋嬫墽琛?+ JSONL 澧為噺鍏ュ簱 |
| News 鎻愬彇 | `core/crawler/news.py` | 鉁?宸茶惤鍦?| HTTP 鎴栨湰鍦?ExtractorService |
| 璺ㄥ钩鍙版爣鍑嗗寲 | `core/crawler/normalizer.py` | 鉁?宸茶惤鍦?| media_urls/hashtags/external_links 缁熶竴 |
| 寮傛閲囬泦浠诲姟 | `tasks/crawl_tasks.py` | 鉁?宸茶惤鍦?| Celery 鎵ц |

API锛歚GET /crawl/platforms`銆乣POST /crawl/social`銆乣GET /crawl/jobs`銆乣GET /crawl/data`銆?
---

## 4. 鍔熻兘涓€ 路 鍗忓悓鍙戠幇锛圞T1锛夆€?鏍稿績鍏抽敭鎶€鏈?
### 4.1 鍔熻兘璁捐

鍦ㄤ簨浠剁獥鍙ｅ唴璇嗗埆"鍏卞悓鎺ㄥ姩鏌愬彊浜?鐨勫崗鍚岃处鍙风兢浣擄紝杈撳嚭鍗忓悓杈?+ 璇佹嵁 + 鍗忓悓缇ょ粍銆?*涓ら樁娈垫鏋?*锛圡annocci 2024 缁艰堪锛夛細

- **Detection锛堝彂鐜?璋佸湪鍗忓悓"锛?* 鈥斺€?Coordination Discover 鏍稿績鍒涙柊鎵€鍦?- **Characterization锛堝埢鐢?鍗忓悓缇や綋鏄粈涔堟牱"锛?* 鈥斺€?鍥涚淮琛ㄥ緛锛欰uthenticity / Orchestration / Time-variance锛堣涓?缁撴瀯鍨嬶紝Coordination Discover锛? Harmfulness锛堝唴瀹瑰瀷锛屽綊 Risk Review锛?
### 4.2 鍏抽敭鎶€鏈笌鍒涙柊瀹氫綅锛?026-06-02 鏈€鏂版柟鍚戯級

**璺ㄥ钩鍙板崗鍚屽彂鐜帮細鍙敤骞冲彴鏃犲叧鐨?鍏卞悓琛屼负鐗瑰緛"鍋氬鐢ㄨ瀺鍚堟娴嬶紱鍐呭妫€娴嬩笉浣滀负鍗忓悓淇″彿銆?*

- 绔嬭锛氱幇鏈?CIB 鏂囩尞渚濊禆骞冲彴鐗瑰畾淇″彿锛坈otweet/retweet/cofollow/time burst锛夛紝澶氬獟浣撳钩鍙板張鎻愪笓鐢ㄥ唴瀹逛俊鍙凤紙瑙嗛-璇箟 mismatch锛夆€斺€斿唴瀹逛俊鍙峰钩鍙扮壒瀹氥€佹槗琚?AI 鏀瑰啓銆佽縼绉绘垚鏈珮
- 鍏卞悓琛屼负淇″彿锛氭椂闂村悓姝?鍏辩幇銆佸叡浜璞★紙URL/hashtag/濯掍綋鎸囩汗 id锛夈€佸叡杞彂涓庡洖澶嶇骇鑱斻€佽处鍙疯涓鸿妭寰?- 琛屼负 vs 鍐呭杈圭晫鍒ゆ嵁锛?*鏄惁闇€瑕?鐞嗚В鍐呭璇翠簡浠€涔?**銆傚叡浜悓涓€濯掍綋瀵硅薄锛堟寜 id/鎸囩汗锛? 琛屼负锛涘垎鏋愯棰戝唴瀹?瀛楀箷 mismatch/鏂囨湰绔嬪満/姣掓€?= 鍐呭锛堟帓闄わ級
- 鏄捐憲鎬х瓫鏌ワ紙PSL锛夛細瀵圭О瓒呭嚑浣?+ Cauchy combination + pair-level BH-FDR锛屾姂鍒剁儹闂ㄨ瘽棰?鑷劧鍏辨尟"璇姤

### 4.3 钀藉湴鐘舵€?
| 閮ㄥ垎 | 鏂囦欢 | 鐘舵€?|
|------|------|------|
| 鍏变韩瀵硅薄+鏃堕棿绐楅厤瀵癸紙CooRTweet 閲嶅啓锛?| `core/coordination_baseline/detector.py` (184琛? | 鉁?宸茶惤鍦?|
| 鍔犳潈鍥?+ 鐧惧垎浣嶉槇鍊?+ 绀惧尯鍙戠幇 | `core/coordination_baseline/network.py` (373琛? | 鉁?宸茶惤鍦?|
| 璐︽埛/缇ょ粍缁熻 | `core/coordination_baseline/stats.py` (142琛? | 鉁?宸茶惤鍦?|
| PSL 鏄捐憲鎬э紙瓒呭嚑浣?Cauchy+BH-FDR锛?| `significance.py` | 鉂?**璁捐绋匡紝0 琛?* |
| 澶氳涓洪€氶亾鎶藉彇 | `channels.py` | 鉂?**璁捐绋匡紝0 琛?* |
| 璇箟閫氶亾 | `semantic.py` | 鉂?璁捐绋匡紙涓旀柊鏂瑰悜鍊惧悜鎺掗櫎锛?|

API锛歚POST /coordination/detect`銆?
### 4.4 绛旇京椋庨櫓锛堥』鐭ワ級

- 鍒涙柊涓诲紶"琛屼负浼樺厛/骞冲彴鏃犲叧"宸茶 Schneider/Rizoiu *Beyond Content*(arXiv 2602.02838)銆丩uceri *CIB on TikTok*(2505.10867) 鍋氬嚭 鈫?**涓嶈兘褰撳師鍒涢鍙?*锛屽敮涓€鍙京鎶?delta 鏄?PSL 缁熻妗嗘灦锛屼絾 0 琛屼唬鐮?- "璺ㄥ钩鍙?浠呴獙璇?mock_weibo/weibo/news锛堣法婧愰潪璺ㄥ钩鍙拌韩浠斤級锛岄』鏀瑰彛寰?- 鎺掗櫎鍐呭淇″彿鍦ㄥ崟骞冲彴涓婃槸 tradeoff锛堝彲鑳界暐鎹熷彫鍥烇級锛屼笉鏄函澧炵泭

---

## 5. 鍔熻兘浜?路 浼犳挱鐩戞帶锛圞T2锛?
### 5.1 鍔熻兘璁捐

棰勬祴浜嬩欢瑙勬ā涓庝紶鎾€佸娍锛屽姛鑳藉眰鍊熼壌"鐭ュ井"(Zhiwei) 浼犳挱鍒嗘瀽浜у搧鐨?*鍛堢幇褰㈡€?*锛堝彲瑙嗗寲/鍔熻兘褰㈡€侊紝闈炲垱鏂版潵婧愶級銆?
> **鑱岃矗杈圭晫锛?026-06-03 鍘樻竻锛?*锛欿T2 **鍙仛浼犳挱鍔ㄥ姏瀛?*锛堣妯?褰㈡€?璺緞棰勬祴锛夛紝**涓嶅仛鍐呭鍒嗘瀽**銆傜珛鍦烘娴嬨€佸嵄瀹虫€ц瘎浼扮瓑鍐呭鐞嗚В浠诲姟**宸插叏閮ㄧЩ浜?Risk Review 鐨?Characterization 灞?*锛孠T2 涓嶅啀鎵胯浇锛屼互娑堥櫎涓?Risk Review 鐨勮亴璐ｉ噸鍙犮€?
瀛愬姛鑳斤細

- **鍒嗗眰浼犳挱棰勬祴**锛堝叧閿妧鏈級锛氬畯瑙傝妯?+ 涓璺緞褰㈡€?+ 寰涓嬩竴璺筹紝涓夊眰鍏辩敤鍚屼竴浜嬩欢/浣撳埗鍚庨獙
- 浼犳挱鎬佸娍鍒荤敾锛氬瓙鍥俱€佹椂闂寸嚎銆佽捣鐖?妗ユ帴/鎵╂暎鍏抽敭瑙掕壊锛堝瓙鍔熻兘锛屽凡钀藉湴锛?- 婧愬ご杩芥函涓庤瘉鎹摼銆佸叧閿矾寰?*鍥炴函**锛堝瓙鍔熻兘锛屽凡钀藉湴锛涙敞鎰忔槸浜嬪悗鍥炴函锛岄潪棰勬祴锛?- ~~绔嬪満妫€娴?/ 鍗卞鎬ц瘎浼皛~ 鈫?**绉讳氦 Risk Review**锛堣 搂6.1锛?
### 5.2 鍏抽敭鎶€鏈細浜嬩欢鏉′欢涓嬬殑鍒嗗眰浼犳挱棰勬祴妗嗘灦

鏍稿績涓荤嚎锛氱敤 LLM 鎶婂笘瀛愬唴瀹规娊鎴?*澶栫敓浜嬩欢**锛岄┍鍔ㄩ€忔槑鐨?*浣撳埗鍚庨獙 p(z|events,history)**锛屽苟浠ヨ鍚庨獙**鍚屾椂鏉′欢鍖?*涓変釜灏哄害鐨勪紶鎾娴嬨€傚尯鍒簬鐭ュ井锛堜粎浜嬪悗鍒嗘瀽銆佹棤棰勬祴锛変笌鐜版湁绾ц仈妯″瀷锛堜粎鐢ㄨ娴嬪簭鍒椼€佹棤澶栫敓浜嬩欢鏉′欢锛夈€?
```
LLM 浜嬩欢鎶藉彇 鈹€鈹€鈫?浣撳埗鍚庨獙 p(z|events,history)   鈫?CascadeSwitch 鏍稿績锛屽凡钀藉湴
                      鈹?        鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹尖攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?        鈻?            鈻?                          鈻?   Tier-0 瀹忚     Tier-1 涓                Tier-2 寰
   瑙勬ā棰勬祴 欧      璺緞褰㈡€侀娴?              涓嬩竴璺抽娴?   (鏍囬噺,宸茶惤鍦?   P(涓績鍖?鍘讳腑蹇冨寲/          P(涓嬩竴婵€娲昏妭鐐?v |
                  璺ㄧ兢妗ユ帴 | z,events)          搴忓垪, 鏉′欢浜?p(z))
   闆惰缁冪櫧鐩?     闆惰缁冪櫧鐩?鏂板)            璁粌寮?鏂板)
```

- **Tier-0 瑙勬ā棰勬祴锛圕ascadeSwitch锛屽凡钀藉湴锛?*锛? 浣撳埗锛坰eeding/amplification/peak/decay锛塻oftmax 鍚庨獙娣峰悎棰勬祴锛岄浂璁粌銆佸彲瑙ｉ噴銆佸甫缃俊鍖洪棿
- **Tier-1 璺緞褰㈡€侀娴嬶紙鏂板锛岄浂璁粌锛?*锛氭瘡涓綋鍒堕厤缁撴瀯鍏堥獙锛坰eeding鈫掑幓涓績鍖栨暎鎾?/ amplification鈫掍腑蹇冨寲鏋㈢航 / coordinated_burst鈫掕法缇ゆˉ鎺ワ級锛屽鐢?W 鐭╅樀鍚庨獙锛屼笌瑙勬ā棰勬祴鍚屾簮
- **Tier-2 寰涓嬩竴璺抽娴嬶紙鏂板锛岃缁冨紡锛?*锛氬皢浣撳埗鍚庨獙 p(z) 浣滀负鏉′欢杈撳叆鍠傜粰涓嬩竴璺抽娴嬪櫒 = **event/regime-conditioned next-node prediction**銆傜湡 delta锛氱幇鏈夊井瑙傛墿鏁ｆā鍨嬶紙Topo-LSTM/NDM/FOREST锛?*鍧囨棤澶栫敓浜嬩欢鏉′欢**锛屾湰妗嗘灦鍦ㄤ綋鍒惰浆鎹㈢偣鏇村噯锛堢敤"鏈?鏃犱簨浠舵潯浠?娑堣瀺璇佹槑锛?
### 5.3 钀藉湴鐘舵€?
| 閮ㄥ垎 | 鏂囦欢 | 鐘舵€?|
|------|------|------|
| 鏃跺簭鐗瑰緛 (WP1) | `core/propagation/ts_features.py` (107) | 鉁?宸茶惤鍦?|
| LLM 浜嬩欢涓婁笅鏂?(WP2) | `core/propagation/llm_context.py` (162) | 鉁?宸茶惤鍦?|
| Tier-0 浣撳埗妯″瀷+棰勬祴鍣?(WP3) | `regime_model.py`(224)+`trend_predictor.py`(180) | 鉁?宸茶惤鍦?|
| 婧愬ご杩芥函/璇佹嵁閾?璺緞鍥炴函 | `core/propagation_legacy.py` (585) | 鉁?宸茶惤鍦帮紙瀛愬姛鑳斤級 |
| Tier-1 璺緞褰㈡€侀娴?| `structure_predictor.py` | 馃敳 鏂板锛堥浂璁粌锛屾帹鑽愬厛鍋氾級 |
| Tier-2 寰涓嬩竴璺抽娴?| 锛堝緟瀹氾級 | 馃敳 鏂板锛堣缁冨紡锛岄渶杈圭骇鐪熷€兼暟鎹級 |
| ~~绔嬪満妫€娴?/ 鍗卞鎬ц瘎浼皛~ | 鈥?| 鉃★笍 **绉讳氦 Risk Review** |

API锛歚GET /propagation/analyze`銆乣POST /propagation/predict-trend`銆?
### 5.4 鍏抽敭鎶€鏈檲杩帮紙绛旇京鍙ｅ緞锛?
> Propagation Analysis 鎻愬嚭**浜嬩欢鏉′欢涓嬬殑鍒嗗眰浼犳挱棰勬祴妗嗘灦**锛氱敤 LLM 鎶婂笘瀛愬唴瀹规娊鎴愬鐢熶簨浠讹紝椹卞姩閫忔槑鐨勪綋鍒跺悗楠?p(z)锛屽苟浠ヨ鍚庨獙鍚屾椂鏉′欢鍖栧畯瑙傝妯°€佷腑瑙傚舰鎬併€佸井瑙備笅涓€璺抽娴嬨€傚尯鍒簬鍟嗕笟浜у搧锛堢煡寰紝浠呬簨鍚庡垎鏋愭棤棰勬祴锛変笌鐜版湁绾ц仈妯″瀷锛堜粎鐢ㄨ娴嬪簭鍒椼€佹棤澶栫敓浜嬩欢鏉′欢锛夈€?
### 5.5 钀藉湴璺緞涓庨闄╋紙璇氬疄锛?
| 灞?| 鐘舵€?| 闇€瑕佸仛 | 鏁版嵁 | 闅惧害 |
|----|------|--------|------|------|
| Tier-0 瑙勬ā | 鉁?宸茶惤鍦?| 鎺ラ€氱湡瀹?LLM锛堝叧鎺?mock_llm锛?| DeepHawkes/CasFlow | 浣?|
| Tier-1 褰㈡€?| 馃敳 鏂板 | 浣撳埗鈫掔粨鏋勫厛楠屾槧灏?+ 褰㈡€佸垎绫?| 澶嶇敤鐜版湁鍥剧壒寰?| 涓紝闆惰缁冿紝**鎺ㄨ崘鍏堝仛** |
| Tier-2 寰 | 馃敳 鏂板 | regime-conditioned 涓嬩竴璺虫ā鍨?+ 璁粌 | Twitter15/16/FOREST 杈圭骇鐪熷€?| 楂橈紝闇€ GPU+娑堣瀺 |

- **鍓嶇疆闃诲**锛歚propagation_service.py` 鐜?`mock_llm=True`锛岄渶鎺ラ€氱湡瀹?LLM锛屽惁鍒?浜嬩欢鏉′欢"鍦?demo 涓嶇敓鏁堬紱鍚庣鏃?LLM 瀹㈡埛绔緷璧栥€乀ier-2 杩橀渶娣卞害瀛︿範妗嗘灦锛岄』鍏堣ˉ `pyproject.toml`
- **Tier-2 鏈€澶т笉纭畾鎬?*锛氫緷璧栬竟绾х湡鍊兼暟鎹紝鐪熷疄閲囬泦涓洪儴鍒嗚娴嬶紝鏁版嵁鏉′欢鍙兘涓嶈冻锛涘繀椤昏窇鍑?鏈?鏃犱簨浠舵潯浠?娑堣瀺鏁板瓧锛屽惁鍒欐拨涓虹焊闈㈠垱鏂?- **鎺ㄨ繘椤哄簭**锛氬厛琛ヤ緷璧?鎺ラ€?LLM 鈫?鍏堣惤 Tier-1锛堜綆椋庨櫓瀹炵墿锛夆啋 鍐嶄笂 Tier-2锛堢暀瓒虫秷铻嶅疄楠屾椂闂达級

---

## 6. 鍔熻兘涓?路 鎶ュ憡鐮斿垽锛圞T3锛?
### 6.1 鍔熻兘璁捐锛堜笁娈碉級

閽堝"鐢?Agent 鍋氭姤鍛婄爺鍒ゅ垱鏂版€у急"鐨勮瘎瀹℃剰瑙侊紝鎶ュ憡鐮斿垽璁捐涓猴細
**(a) 鍩轰簬 Agent 鐨勮瘉鎹紪鎺掞紙鐢ㄦ埛瑷€璁?琛屼负妫€娴嬶級鈫?(b) 鍩轰簬 RAG 鐨勬姤鍛婄敓鎴?鈫?(c) Agent 瑙ｉ噴鎬荤粨鍗忓悓鏀诲嚮**銆?
鍥炵瓟涓変釜闂锛氬綋鍓嶉闄╁楂橈紙淇″康鍖洪棿锛? 鎺ヤ笅鏉ヤ細鍙戠敓浠€涔堬紙闃舵+涓嬩竴姝ユ妧鏈娴嬶級/ 搴旇濡備綍搴斿锛堝弽鍒跺缓璁級銆?
### 6.2 鍏抽敭鎶€鏈細鐧界洅鍓嶇灮寮曟搸锛堝ご鍙峰垱鏂帮級+ 澶?Agent 缂栨帓锛堝憟鐜板眰锛?
> **琛ㄨ堪绾緥**锛氬ご鍙峰垱鏂板繀椤绘槸宸茶惤鍦扮殑鐧界洅绠楁硶锛孉gent/RAG 浠呬綔缂栨帓鍩哄骇涓庡憟鐜板眰锛?*涓嶄綔鍒涙柊鍗栫偣**銆傛牳蹇冨彊浜嬶細浠?detection 鍗囩骇鍒?anticipation + countermeasure銆?
- **Phase-Aware Hazard**锛? 鐘舵€佹垬褰圭敓鍛藉懆鏈?+ logistic hazard 棰勬祴闃舵杞崲/breakout 棰勮
- **DISARM Attack-Path**锛氭妧鏈浆鎹㈠浘璺緞鎺ㄧ悊 + 棰勬祴涓嬩竴姝ユ妧鏈?+ 鍙嶅埗寤鸿锛堥潪 flat tagging锛?- **Contradiction-Aware D-S Fusion**锛氫俊蹇靛尯闂?+ 鍐茬獊妫€娴?+ 闃舵璋冨埗璐ㄩ噺

### 6.3 钀藉湴鐘舵€?
| 灞?| 鏂囦欢 | 鐘舵€?|
|----|------|------|
| Layer 1 璇佹嵁鏋勫缓 | `core/review/evidence_builder.py` (244) | 鉁?宸茶惤鍦?|
| Layer 1 闃舵妫€娴?| `core/review/phase_detector.py` (169) | 鉁?宸茶惤鍦?|
| Layer 1 D-S 铻嶅悎 | `core/review/ds_fusion.py` (234) | 鉁?宸茶惤鍦?|
| Layer 1 DISARM 璺緞 | `core/review/disarm_scorer.py` (381) | 鉁?宸茶惤鍦?|
| Layer 1 鎶ュ憡鐢熸垚 | `core/review/report_builder.py` (278) | 鉁?宸茶惤鍦?|
| LLM 妗ユ帴 | `core/review/llm_bridge.py` (~30) | 鈿狅笍 鍗犱綅锛宺eturn None |
| Layer 2 RAG 鎶ュ憡 | 鈥?| 鉂?璁捐绋?|
| Layer 3 鎭舵剰瑷€璁?绔嬪満/鍙嶅埗鍙欎簨 Agent | 鈥?| 鉂?璁捐绋?|

API锛歚POST /risk/assess`銆乣GET /risk/reports`銆乣GET /risk/reports/{report_id}`銆?
### 6.4 绛旇京椋庨櫓

- 鎶婄爺鍒ゆ墿鎴?鏇村 Agent+RAG"**娌¤В鍐冲弽鑰屽姞閲?*"Agent 鍒涙柊鎬у急"鎵硅瘎锛屼笖鎾?Agentic DISARM(arXiv 2601.15109)銆丟autam 澶?agent 鐢熷懡鍛ㄦ湡(2505.17511)
- 缈荤洏鎴愭湰浣庯紙鍑犱箮鍙姩琛ㄨ堪锛夛細涓荤宸茶惤鍦扮殑鐧界洅寮曟搸锛孉gent/RAG 闄嶇骇
- DISARM"棰勬祴涓嬩竴姝ユ妧鏈?鑼冨紡婧愯嚜 ATT&CK 鍩燂紙MITRE TIE锛夛紝delta 椤绘敹绐勪负"璺ㄥ煙杩佺Щ+闃舵鏉′欢鍖?锛屼笉绉伴鍒?
---

## 7. 妯悜鏀拺妯″潡

| 妯″潡 | 鏂囦欢 | 鐘舵€?| 璇存槑 |
|------|------|------|------|
| 璐︽埛鐩戞祴 | `core/account_profiler.py` (163) | 鉁?宸茶惤鍦?| 琛屼负鐢诲儚 + 鑷姩鍖栧€惧悜璇勫垎锛?-100锛夛紝渚?Coordination Discover/Risk Review 鍙栬瘉 |
| 韬唤璁よ瘉 | `core/security.py` + `services/auth_service.py` | 鉁?宸茶惤鍦?| JWT + bcrypt锛岃鑹?admin/analyst/viewer |
| 鐩戞祴鐪嬫澘 | `services/dashboard_service.py` + `api/v1/dashboard.py` | 馃敡 寮€鍙戜腑 | 鑱氬悎 MongoDB 浜嬩欢鏁版嵁 + ECharts 鍦板浘锛岀儹鐐规帓琛?瓒嬪娍鍥惧緟琛?|
| 棰勮涓績 | 鈥?| 鉂?鏈惎鍔?| 瑙勫垯閰嶇疆銆佷簨浠?缇や綋/claim 绾у憡璀?|
| 鎶ュ憡涓績 | 鈥?| 鉂?鏈惎鍔?| 鎶ュ憡鍒楄〃/瀵煎嚭/妗堜緥褰掓。 |

API锛歚GET /accounts/profiles`銆乣GET /accounts/detail/{id}`銆乣GET /dashboard/overview`銆乣/auth/*`銆?
---

## 8. API 鎬昏锛堝疄闄呮寕杞界殑 7 璺敱缁勶級

| 璺敱缁?| 绔偣 | 閴存潈 |
|--------|------|------|
| auth | `/auth/register` `/login` `/refresh` `/profile` | 閮ㄥ垎 |
| dashboard | `GET /dashboard/overview` | 鏄?|
| crawl | `GET /crawl/platforms` `POST /crawl/social` `GET /crawl/jobs` `GET /crawl/data` | 閮ㄥ垎 |
| coordination | `POST /coordination/detect` | 鏄?|
| accounts | `GET /accounts/profiles` `GET /accounts/detail/{id}` | 鏄?|
| propagation | `GET /propagation/analyze` `POST /propagation/predict-trend` | 鏄?|
| risk | `POST /risk/assess` `GET /risk/reports` `GET /risk/reports/{id}` | 鏄?|
| system | `GET /health` | 鍚?|

> 娉細璺敱 tag 鏄剧ず鍚嶇О锛堝"浼犳挱褰掑洜""椋庨櫓鐮斿垽"锛変负浠ｇ爜鍐呭瓧绗︿覆锛屾枃妗ｅ懡鍚嶅凡缁熶竴涓?浼犳挱鐩戞帶""鎶ュ憡鐮斿垽"锛屼唬鐮?tag 鍚屾灞炰唬鐮佹敼鍔紝鏈湪鏂囨。缁熶竴鑼冨洿鍐呫€?
---

## 9. 鏁翠綋钀藉湴宸窛涓庤法妯″潡鍒嗗伐

### 9.1 涓夋€佹€荤粨

**宸茶惤鍦板彲杩愯**锛氭暟鎹噰闆嗗叏閾捐矾銆佸崗鍚屾娴?MVP锛圕ooRTweet 閲嶅啓+鍥?绀惧尯鍙戠幇锛夈€佷紶鎾秼鍔块娴嬫牳蹇冿紙CascadeSwitch WP1-3锛夈€佹姤鍛婄爺鍒ょ櫧鐩掑紩鎿庯紙Layer 1 绾?1340 琛岋級銆佽处鎴风敾鍍忋€佽璇併€佺湅鏉块洀褰€?
**璁捐绋匡紙鏈夋柟妗堟棤浠ｇ爜锛?*锛欿T1 鐨?PSL/澶氶€氶亾銆並T3 鐨?Agent 缂栨帓/RAG 鎶ュ憡/Layer 3 Agent銆並T2 鐨勭珛鍦?鍗卞瀛愬姛鑳姐€?
**缂哄彛锛堟棤璁捐鏃犱唬鐮侊級**锛欿T2 浼犳挱璺緞棰勬祴锛堟湭鏉ョ粨鏋勶級銆侀璀︿腑蹇冦€佹姤鍛婁腑蹇冦€佽瘎浼拌剼鏈笌鍏紑鏁版嵁闆嗗熀鍑嗐€?
### 9.2 涓夋潯鍏辨€ч樆濉?
1. **LLM 瀹㈡埛绔緷璧栫己澶?* 鈥斺€?`pyproject.toml` 鏃犱换浣?LLM SDK銆傞樆濉?Propagation Analysis 鐪熷疄浜嬩欢鎻愬彇锛堢幇 `mock_llm=True`锛? Risk Review Agent 灞傘€傞渶鍏堝畾 DeepSeek 鎺ュ叆骞惰ˉ渚濊禆銆?2. **缁熻/绠楁硶渚濊禆缂哄け** 鈥斺€?鏃?scipy/statsmodels锛岄樆濉?Coordination Discover PSL 钀藉湴銆?3. **鏃犺瘎浼伴棴鐜?* 鈥斺€?涓夋ā鍧楀潎鏃犲熀鍑嗘暟鍊硷紝"瓒呰秺 SOTA"绫诲绉版殏鏃犲疄璇併€?
### 9.3 璺ㄦā鍧楀垎宸ワ紙鍐呭鍒嗘瀽褰掑睘锛岄棴鐜渶澶ц缂濈殑缁熶竴鍙ｅ緞锛?
> 绛旇京鏈€鑷村懡涓€棰樻槸"鍐呭鍒嗘瀽褰掕皝"銆傜粺涓€鍙ｅ緞濡備笅锛屼笁妯″潡琛ㄨ堪蹇呴』涓€鑷达細

- **鍐呭鍒嗘瀽锛堢珛鍦?鍗卞/鏈夊瑷€璁猴級鍞竴褰掑 = Risk Review 鐨?Characterization**
- **Coordination Discover 绾涓?*锛氬埢鎰忕殑椴佹鎬ц璁★紝鎺掗櫎鍐呭淇″彿锛堟壙璁ゅ崟骞冲彴鍙兘鐣ユ崯鍙洖锛屾崲鍙栬法骞冲彴鍙縼绉讳笌鎶?AI 鏀瑰啓锛?- **Propagation Analysis 鍙仛浼犳挱鍔ㄥ姏瀛?*锛氳妯?浣撳埗棰勬祴锛屼笉纰板唴瀹瑰垎绫?- **鍐呭淇″彿鍗曞悜娴佸姩**锛氫粠涓嬫父娑堣垂锛岀粷涓嶅洖娴佷綔涓哄崗鍚屽垽瀹氫緷鎹?- 鍔犲垎椤癸細Propagation Analysis 棰勬祴"浼犳挱浼氭定澶氬ぇ"銆並T3 棰勬祴"鏀诲嚮鑰呬笅涓€姝ョ敤浠€涔堟墜娉?锛屼袱濂楅娴嬩簰琛ヤ笉鍐茬獊

### 9.4 闂幆鏁版嵁娴侊紙鏈嶅姟灞傛帴缂濓級

```
crawl 鈫?MongoDB(raw_posts/comments)
  鈫?coordination_service.detect 鈹€鈹?  鈫?propagation_service.analyze 鈹€鈹尖攢鈫?risk_service.assess_risk
  鈫?account_service.profiles 鈹€鈹€鈹€鈹€鈹?   (evidence_builder 鈫?phase_detector
                                        鈫?ds_fusion 鈫?disarm_scorer 鈫?report_builder)
```
鐪熷疄鎺ョ紳瑙?`services/risk_service.py` 鐨?`assess_risk()`锛氫緷娆¤皟鍗忓悓/浼犳挱/璐︽埛涓?service锛屾眹鑱氳瘉鎹寘鍚庝覆璧烽樁娈垫娴嬧啋铻嶅悎鈫扗ISARM鈫掓姤鍛娿€?
---

## 10. 鍙傝€冧笌寤朵几

- 鍚勬妧鏈嚎鏂瑰悜鑳屾櫙锛歚doc/research/key-technology-background/{coordination-detection,propagation-analysis,risk-disarm,overview}.md`
- 宸ョ▼杩涘害锛歚doc/engineering/development-roadmap.md`銆乣development-log.md`
- 绛旇京椋庨櫓涓庢枃鐚牳楠岋細`tmp/defense-review/{coordination-discover,propagation-analysis,risk-review}-findings.md`銆乣examiner-review.md`銆乣novelty-validation.md`
- 鍏抽敭鎾炶溅鏂囩尞锛欱eyond Content(2602.02838)銆丆IB on TikTok(2505.10867)銆丆asFT(2409.16619)銆丄utoCas(2502.18040)銆丄gentic DISARM(2601.15109)銆丮ulti-agent Misinformation Lifecycle(2505.17511)

