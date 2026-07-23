# 鍏抽敭鎶€鏈竴锛氳法骞冲彴鍗忓悓鍙戠幇锛堝叡鍚岃涓虹壒寰佸鐢ㄨ瀺鍚堟娴嬶級

> **鐢ㄩ€?*锛氬畾涔?Coordination Discover 鐨勭爺绌堕棶棰樸€佸綋鍓嶅伐绋嬭惤鐐广€佺爺绌剁洰鏍囥€佸疄鐜版柟鍚戝拰楠岃瘉鏂瑰紡銆? 
> **鍙椾紬**锛欳oordinationDiscover 鐮旂┒瀹炵幇鑰呫€佸崗鍚屾娴嬫ā鍧楃淮鎶よ€呫€? 
> **缁存姢瑙勫垯**锛氬彧鍐欏叧閿妧鏈儗鏅笌鐮旂┒鏂规锛涗骇鍝佹帴鍙ｅ拰浠诲姟鐘舵€佹斁鍏?`../../engineering/`銆?
> 鏂瑰悜鏇存柊锛?026-06-02锛夛細Coordination Discover 鏄湰椤圭洰鏍稿績鍏抽敭鎶€鏈€傛渶鏂板畾浣嶄负 **璺ㄥ钩鍙板崗鍚屽彂鐜扳€斺€斿埄鐢ㄥ钩鍙版棤鍏崇殑鈥滃叡鍚岃涓虹壒寰佲€濆仛澶嶇敤铻嶅悎妫€娴嬶紱鍏蜂綋鐨勫唴瀹规娴嬩笉浣滀负鍗忓悓鍙戠幇鐨勪俊鍙?*銆?> 绔嬭锛氱幇鏈?CIB 妫€娴嬫枃鐚ぇ澶氫緷璧栫壒瀹氬崗鍚屼俊鍙凤紙cotweet/retweet/cofollow/time burst锛夛紱闈㈠悜鎶栭煶绛夊濯掍綋骞冲彴鍙堟彁鍑烘洿涓撶敤鐨勫唴瀹瑰瀷淇″彿锛堝瑙嗛-璇箟 mismatch锛夛紝杩欑被鍐呭淇″彿骞冲彴鐗瑰畾銆佹槗琚敓鎴愬紡 AI 鏀瑰啓銆佽法骞冲彴杩佺Щ鎴愭湰楂樸€侰oordinationDiscover 杞€屽彧鐢ㄥ悇骞冲彴鍏辨湁銆佸彲杩佺Щ鐨勮涓虹壒寰佷綔涓哄崗鍚屽垽鎹€?
> 鏂瑰悜鏇存柊锛?026-06-26锛夛細Coordination Discover 涓嶅啀瀹氫綅涓虹函缃戠粶绉戝鏂规硶锛岃€屾槸 **GNN + LM 澧炲己鐨勫崗鍚岀ぞ鍖烘瀯寤轰笌鍙戠幇鏂规硶**銆傜綉缁滅瀛︽寚鏍囦粛鐢ㄤ簬鍙В閲婅瘎浼颁笌绀惧尯璐ㄩ噺瀹¤锛屼絾鏍稿績妯″瀷搴斾粠闈欐€佸姞鏉冨浘鍗囩骇涓猴細LM 鎻愪緵鍏变韩瀵硅薄/鑺傜偣/绀惧尯鐨勮涔夎〃寰佷笌楂樺奖鍝嶈妭鐐规爣娉紝GNN 鍦ㄥ鍏崇郴銆佸姩鎬併€佹湁鍚戝崗鍚屽浘涓婅繘琛屾秷鎭紶閫掋€佸叧绯昏瀺鍚堝拰绀惧尯琛ㄧず瀛︿範銆?
## 1. 闂瀹氫箟

鍦ㄤ簨浠剁獥鍙ｅ唴锛岃瘑鍒竴缁勫湪璇ョ獥鍙ｅ唴鍏卞悓鎺ㄥ姩鏌愬彊浜嬬殑璐﹀彿闆嗗悎锛堝崗鍚岀兢浣擄級锛屽苟杈撳嚭鍙В閲婄殑鍗忓悓杈逛笌璇佹嵁鏍锋湰銆傛牳蹇冨師鍒欙細**鍗忓悓鍒ゅ畾鍙湅鈥滆涓烘槸鍚﹀悓姝モ€濓紝涓嶇湅鈥滃唴瀹硅浜嗕粈涔堚€?*銆傚唴瀹圭悊瑙ｏ紙绔嬪満/鍗卞/鍥炬枃涓€鑷达級鍗曞悜涓嬫矇鍒颁笅娓?Propagation Analysis/Review锛岀粷涓嶅洖娴佷綔涓哄崗鍚屼俊鍙枫€?
Coordination Discover 鐨勭爺绌朵换鍔￠噰鐢ㄤ袱闃舵瀹氫箟锛?
1. **鍗忓悓鍙戠幇**锛氫粠骞冲彴鏃犲叧鐨勫叡鍚岃涓轰簨浠朵腑鏋勫缓澶氬叧绯诲崗鍚屽浘锛屽苟鐢?GNN + LM 瀛︿範鐢ㄦ埛銆佸叡浜璞″拰绀惧尯鐨勮〃绀猴紝鍙戠幇鍗忓悓璐﹀彿绨囥€佸叧閿处鍙峰鍜屽叡浜璞°€傝闃舵瀵瑰簲 coordinated online behavior / information operations detection 鏂囩尞涓殑 community 鎴?cluster 杈撳嚭銆?2. **鍗忓悓鍖哄垎**锛氬湪鏈?IO/control 鎴?coordinated/organic 鏍囩鐨勬暟鎹泦涓婏紝妫€楠岀涓€闃舵寰楀埌鐨勫崗鍚屽浘淇″彿鏄惁鑳藉鍖哄垎鑷彂琛屼负鍜屽崗鍚屾敾鍑汇€傝闃舵鎵嶈繘鍏ユ帓搴忔垨鍒嗙被璇勪及銆?
鍥犳锛孋oordinationDiscover 涓嶆槸浠?bot detection銆乼roll identification 鎴?misinformation classification 涓轰富浠诲姟銆傜浉鍏抽鍩熺殑鎸囨爣鍙綔涓?auxiliary characterization锛岀敤浜庤В閲婂崗鍚岀兢浣撶殑鐪熷疄鎬с€佺粍缁囨€с€佸嵄瀹虫€ф垨鏃跺簭妯″紡銆?
瑕佽ˉ榻愮殑鑳藉姏锛?
- 澶氱鍏卞悓琛屼负淇″彿鐨勭粺涓€寤烘ā涓庤瀺鍚堬紙鏃堕棿鍚屾銆佸叡浜璞°€佸叡杞彂绾ц仈銆佽涓鸿妭寰嬬瓑锛?- LM 澧炲己鐨勫叡浜璞″綊涓€鍖栥€佽妭鐐?绀惧尯璇箟琛ㄥ緛鍜岄珮褰卞搷鍔涜妭鐐规爣娉?- GNN 鍦ㄥ鍏崇郴銆佸姩鎬併€佹湁鍚戝崗鍚屽浘涓婄殑娑堟伅浼犻€掋€佸叧绯?attention 涓庣ぞ鍖鸿〃绀哄涔?- 鑷劧鍏辨尟 vs 浜轰负鍗忓悓鐨勬樉钁楁€х瓫鏌ワ紙鎶戝埗鐑棬璇濋璇姤锛?- 鍙В閲婄殑杈圭被鍨嬩笌璇佹嵁鏍锋湰杈撳嚭
- 璺ㄥ钩鍙?璺ㄦ簮鐨勪俊鍙峰彲澶嶇敤鎬?

### 1.1 Discover / Detect 浠诲姟杈圭晫锛?026-06-28 鍥哄寲锛?
Coordination Discover 姝ｅ紡閲囩敤 **Discover -> Detect** 涓ら樁娈靛彛寰勶紝浜岃€呬笉鑳芥贩鐢ㄨ瘎浠锋寚鏍囥€?
| 闃舵 | 浠诲姟瀹氫箟 | 鏄惁浣跨敤鏍囩 | 涓昏杈撳嚭 | 涓昏瘎浠锋寚鏍?|
|---|---|---:|---|---|
| Discover | 鏃犳爣绛惧崗鍚岀ぞ鍖哄彂鐜帮細浠庡叡鍚岃涓轰簨浠朵腑鍙戠幇鍝簺璐﹀彿鍥寸粫鍝簺瀵硅薄銆侀€氳繃鍝簺鍏崇郴銆佸湪浠€涔堟椂闂寸獥鍙ｅ唴褰㈡垚鍙В閲婂崗鍚岀ぞ鍖?| 鍚?| `cluster_id`銆乣edge_score`銆乣community_score`銆乣top_objects`銆乣relation_breakdown`銆乣object_concentration`銆乣dynamic_edges`銆乣metapath_attention` | `modularity`銆乣conductance`銆乣density`銆乣object_concentration`銆乣relation_entropy`銆佹椂闂寸獥/澶氬昂搴?`NMI/ARI/Jaccard` |
| Detect | 鏈夋爣绛惧崗鍚屽尯鍒嗭細鍒ゆ柇璐﹀彿鎴栫ぞ鍖烘槸鍚﹀睘浜?IO driver / coordinated attacker / organic user | 鏄?| `node_score`銆乣predicted_label`銆乣community_detection_score`銆佽处鍙?绀惧尯绾ф帓搴?| `AP/AUC/AUPRC`銆乣MaxF1`銆乣Precision@K`銆乣Recall@K` |

AMDN-HAGE 绛夋枃鐚眹鎶ョ殑 `AP / AUC / F1@0.5 / Precision@0.5 / Recall@0.5 / MaxF1` 鏄处鍙风骇妫€娴嬫寚鏍囷紝琛￠噺鈥滃崟涓处鍙锋槸鍚﹀崗璋?鍙枒鈥濈殑鍒ゆ柇鑳藉姏锛涜繖浜涙寚鏍囧睘浜?Detect锛屼笉鐢ㄤ簬璇佹槑 Discover 鐨勭ぞ鍖哄垝鍒嗚川閲忋€侰oordinationDiscover 姝ｅ紡 Detect 涓昏〃閲囩敤 `MaxF1` 浣滀负 F1 绫讳富鎸囨爣锛屽浐瀹氶槇鍊?`F1@0.5` 浠呬綔涓洪槇鍊兼牎鍑嗚瘖鏂紝涓嶇敤浜庢柟娉曟帓鍚嶃€?
Discover 闃舵浣跨敤 Leiden 鐨勫師鍥犳槸锛歀eiden 鏄垚鐔熺殑鏃犵洃鐫?weighted graph 绀惧尯鍒掑垎鍚庣锛屾瘮 Louvain 鏇磋兘閬垮厤涓嶈繛閫氭垨浣庤川閲忕ぞ鍖猴紱瀹冧笉鏇夸唬 MAGNN锛岃€屾槸鍦?MAGNN 瀛﹀埌 `node embedding / edge_score / metapath_attention` 鍚庯紝灏嗛噸鍔犳潈鍗忓悓鍥惧垏鍒嗕负鍙璁＄ぞ鍖恒€侺eiden 鐨勭粨鏋滃簲浣滀负 Detect 鐨勭粨鏋勫寲杈撳叆鐗瑰緛锛屼緥濡?`cluster_id`銆乣community_size`銆乣community_score`銆乣density`銆乣object_concentration`銆乣relation_breakdown`銆乣edge_score`銆乣discover_embedding`锛屼絾涓嶈兘鐩存帴褰撲綔 Detect 鐨勭湡鍊兼爣绛俱€?
楂樻按骞?IO/璐﹀彿妫€娴嬫枃鐚笉鏅亶浣跨敤 Leiden锛屼富瑕佹槸鍥犱负浠诲姟涓嶅悓锛欰MDN-HAGE銆乁nmasking銆両OHunter 绛夋牳蹇冪洰鏍囨槸璐﹀彿绾ф垨 driver 绾?detection锛屼富闂鏄垎绫汇€佹帓搴忔垨璺ㄨ鍔ㄦ硾鍖栵紱鑰屾垜浠殑 Discover 闃舵鐩爣鏄?label-free coordinated community discovery锛屽洜姝ら渶瑕佷竴涓槑纭€佺ǔ瀹氥€佸彲瑙ｉ噴鐨勭ぞ鍖哄垝鍒嗗悗绔€傛垜浠殑鍒涙柊鐐逛笉鍦ㄢ€滃彂鏄?Leiden鈥濓紝鑰屽湪鍔ㄦ€佸鍏崇郴 User-Object-User 鍥俱€丮AGNN 杈圭疆淇″害瀛︿範銆佸璞＄骇璇佹嵁杈撳嚭锛屼互鍙婂皢 Discover 绀惧尯缁撴瀯浼犻€掔粰 Detect銆?
Detect 闃舵鐨勬寮忎富绾垮弬鑰?IOHunter / SocGFM锛岃€屼笉鏄户缁娇鐢?Leiden 鍋氬垎绫汇€傚綋鍓嶅疄鐜板皢 `gfm_lm_gnn` 瀹氫綅涓鸿鏂囦富妯″瀷锛氬厛澶嶇敤 Discover 鐨?MAGNN `discover_embedding`銆乣edge_score`銆乣cluster_id/community_score`銆佸叧绯讳笌鍏冭矾寰勭粺璁★紱鍐嶆嫾鎺?LM/SBERT 鎴?`tfidf_object_bag_fallback` 璇箟鐗瑰緛锛涙渶鍚庡湪 Discover 閲嶅姞鏉冪殑澶氬叧绯诲浘涓婅缁冪洃鐫ｅ紡 LM+GNN/GFM 妫€娴嬪櫒銆俙fusion_gnn`銆乣relation_gnn` 鍜?`classifier` 淇濈暀涓?Detect baseline銆傝嫢 IOHunter processed 鏁版嵁缂哄皯鐪熷疄鏂囨湰锛孡M 鍒嗘敮鍙兘澹版槑涓?metadata/object bag semantic feature锛屼笉鑳藉じ澶т负瀹屾暣 LLM 璐＄尞銆?
## 2. 褰撳墠浠ｇ爜鍩虹嚎

褰撳墠浠ｇ爜钀界偣锛?
- `system/backend/app/core/coordination_baseline/`锛坄detector.py` / `network.py` / `stats.py`锛?- `system/backend/app/services/coordination_service.py`
- `system/backend/app/api/v1/coordination.py`

褰撳墠宸插疄鐜帮紙鐪熷疄鍙繍琛岋級锛?
- 鍏变韩瀵硅薄 + 鏃堕棿绐楅厤瀵癸紙CooRTweet 閲嶅啓锛宍detector.py`锛?- 鍔犳潈鏃犲悜鍥?+ 鐧惧垎浣嶉槇鍊硷紙`network.py`锛?- 璐︽埛绾?/ 缇や綋绾х粺璁°€佺ぞ鍖哄彂鐜般€佺綉缁滃簭鍒楀寲涓庡墠绔彲瑙嗗寲

褰撳墠鏈疄鐜版垨浠呭師鍨嬪疄鐜帮細

- **PSL锛圥air Surprisal Layer锛夋樉钁楁€х瓫鏌?*锛氬绉拌秴鍑犱綍 + Cauchy combination + pair-level BH-FDR锛坄significance.py` 涓嶅瓨鍦級
- 澶氳涓洪€氶亾鎶藉彇涓庤瀺鍚堬紙`channels.py` 涓嶅瓨鍦級
- LM 琛ㄥ緛灞傦紙`semantic.py` 涓嶅瓨鍦級锛氱敤浜?object canonicalization銆佽妭鐐?绀惧尯琛ㄧず銆丯ode Selection 鍚庣殑 LLM annotation锛涗笉鑳芥妸鈥滄枃鏈珛鍦?鍗卞鍒嗙被鈥濈洿鎺ュ綋浣滃崗鍚岃竟璇佹嵁
- GNN 鍗忓悓绀惧尯鍙戠幇灞傦細褰撳墠 `twitter_io_experiment.py` 浠呮湁杞婚噺 learnable relation attention 鍘熷瀷锛岃繕涓嶆槸瀹屾暣鐨勫鍏崇郴鍥炬秷鎭紶閫掓ā鍨?
## 3. 杩欎竴鎶€鏈嚎瑕佽В鍐崇殑鏍稿績闂

- 鍝簺琛屼负鐗瑰緛鏄法骞冲彴鍙鐢ㄧ殑锛堜笉渚濊禆鍗曞钩鍙扮壒鏈夋満鍒躲€佷笉渚濊禆璇绘噦鍐呭锛?- 濡備綍鎶婁笉鍚岀被鍨嬬殑琛屼负鍗忓悓杈圭粺涓€鎶曞奖鍒拌处鍙峰崗璋冨浘锛屽苟閫氳繃 GNN 瀛︿範鍏崇郴鏉冮噸銆佽妭鐐硅〃绀哄拰绀惧尯杈圭晫
- 濡備綍浣跨敤 LM 杩涜鍏变韩瀵硅薄褰掍竴鍖栥€佽涔変笂涓嬫枃鍘嬬缉鍜岄珮褰卞搷鍔涜妭鐐规爣娉紝鑰屼笉鎶婃櫘閫氬唴瀹瑰垎绫昏褰撴垚鍗忓悓璇佹嵁
- 濡備綍鐢ㄦ樉钁楁€х瓫鏌ュ尯鍒嗚嚜鐒跺叡鎸笌浜轰负鍗忓悓
- 濡備綍杈撳嚭鍙В閲婄殑杈圭被鍨嬭瘉鎹紝鑰屼笉鍙槸涓€涓粦鐩掑垎鏁?
## 4. 鎺ㄨ崘瀹炵幇鏂瑰悜

- 鍗忓悓淇″彿鍙彇鈥滃叡鍚岃涓虹壒寰佲€濓細鏃堕棿鍚屾/鍏辩幇銆佸叡浜璞★紙URL/hashtag/濯掍綋鎸囩汗 id锛夈€佸叡杞彂涓庡洖澶嶇骇鑱斻€佽处鍙疯涓鸿妭寰嬨€佸叡鍙備笌妯″紡绛?- 琛屼负 vs 鍐呭鐨勮竟鐣屽垽鎹細鍏变韩鍚屼竴濯掍綋瀵硅薄锛堟寜 id/鎸囩汗锛? 鍗忓悓璇佹嵁锛汱M 瀵瑰璞℃弿杩般€乁RL 鏍囬銆佹ā鏉挎枃鏈€佽妭鐐瑰巻鍙茶繘琛岃〃寰?= 琛ㄧず澧炲己锛涘垎鏋愯棰戝唴瀹?瀛楀箷 mismatch/鏂囨湰绔嬪満/姣掓€?= 涓嬫父 Characterization锛屼笉鐩存帴浣滀负鍗忓悓杈硅瘉鎹?- 绗竴鐗堝伐绋嬪彲浠ヤ繚鐣?pandas/numpy/networkx 杞婚噺閾捐矾浣滀负鍙В閲?baseline锛屽悓鏃舵妸 `twitter_io_experiment.py` 涓殑 learnable relation attention 鍙戝睍涓哄鍏崇郴 GNN encoder锛氳緭鍏?relation-specific edge features銆丩M node/object embeddings 鍜屾椂闂寸壒寰侊紝杈撳嚭 edge score銆乶ode embedding銆乧ommunity assignment
- 浣跨敤 Node Selection + LLM annotation锛氬厛鎸夊嚭搴?鍏ュ害/鍔犳潈搴?PageRank/璺ㄧ皣妗ユ帴鎬ч€夐珮褰卞搷鑺傜偣锛屽啀璁?LLM 鏍囨敞鍏惰鑹层€佸叡浜璞′富棰樺拰鐤戜技缁勭粐鍔熻兘锛汱LM 鏍囨敞鐢ㄤ簬瑙ｉ噴鍜屽急鐩戠潱锛屼笉鏇夸唬琛屼负璇佹嵁
- 鏄犲皠鍒?Mannocci 2024 缁艰堪鐨?Detection + Characterization 涓ら樁娈碉細琛屼负鍚屾 = Detection锛圕oordinationDiscover 鏍稿績锛夛紱鍐呭/姣掓€?绔嬪満 = Characterization 鎴栦笅娓?Propagation Analysis/Review
- 琛ㄨ堪绾緥锛氣€滆法骞冲彴鈥濆綋鍓嶄粎楠岃瘉 mock_weibo/weibo/news锛堣法婧愶紝闈炶法骞冲彴韬唤瑙ｆ瀽锛夛紝瀵瑰搴旇〃杩颁负鈥滃钩鍙版棤鍏崇殑琛屼负淇″彿璁捐 + 璺ㄦ簮楠岃瘉鈥濓紝骞跺潶鐧藉崟骞冲彴涓婃帓闄ゅ唴瀹逛俊鍙锋槸椴佹鎬?tradeoff锛堝彲鑳界暐鎹熷彫鍥烇紝鎹㈠彇鍙縼绉绘€т笌鎶?AI 鏀瑰啓锛?
## 5. 鎺ㄨ崘楠岃瘉鏂瑰紡

姝ｅ紡瀹為獙鍒嗕负涓ょ被锛?
- **Setting A: discovery-only**銆備娇鐢?X/Twitter Information Operations Archive锛岀洰鏍囨槸璇佹槑鏂规硶鑳戒粠姝ｆ牱鏈?IO 妗ｆ涓彂鐜扮粨鏋勬竻鏅般€佽瘉鎹彲瑙ｉ噴鐨勫崗鍚岀綉缁溿€備富鎸囨爣鍖呮嫭 modularity銆乧luster_count銆乴argest_cluster_size銆乨ensity/conductance銆乷bject concentration銆乺elation/channel breakdown銆乼op-K evidence audit 鍜岃法鏃堕棿/璇█/campaign 鍒囩墖鐨勭ǔ瀹氭€с€?- **Setting B: labeled detection**銆備娇鐢?Guo & Vosoughi 2022 state-backed IO dataset 鎴?Seckin et al. 2025 labeled IO datasets锛岀洰鏍囨槸璇佹槑鍗忓悓鍙戠幇闃舵寰楀埌鐨勮竟鏉冦€佺ぞ鍖哄拰缁撴瀯琛ㄥ緛鍙互鍖哄垎 coordinated attack 涓?organic/self-organized behavior銆備富鎸囨爣鍖呮嫭 AUPRC銆丳recision@K銆丷ecall@K銆丮axF1銆丄UROC锛涘浐瀹氶槇鍊?F1 鍙綔涓洪槇鍊艰瘖鏂紝涓嶈繘鍏ヤ富琛紱绀惧尯绾цˉ鍏?FM-score銆丯MI銆丄RI銆丳urity銆?
杈呭姪瀹為獙鍙互鎶ュ憡 bot score銆乼oxicity銆乻tance銆乭armfulness銆乻entiment 绛夎〃寰侊紝浣嗚繖浜涗俊鍙峰彧鐢ㄤ簬 Characterization锛屼笉浣滀负鍗忓悓鍙戠幇鍒ゆ嵁銆?
- `mock_weibo`锛氶獙璇佽涓鸿竟鎷兼帴銆佺粺璁￠€昏緫鍜屽洖褰掓祴璇?- `weibo`锛氶獙璇佺湡瀹為噰闆嗘牱渚嬩笂鐨勮鎶?婕忔姤妯″紡锛堢儹闂ㄨ瘽棰樺帇鍔涙祴璇曪級
- `news`锛氶獙璇佽法婧愬満鏅笅鍏变韩閾炬帴涓庤祫婧愬鐢ㄤ俊鍙?
寤鸿閲嶇偣琛ュ厖锛?
- 鍏卞悓琛屼负杈规瀯寤虹殑鍗曞厓娴嬭瘯
- 鏄捐憲鎬х瓫鏌ョ殑鍥炲綊娴嬭瘯
- 鍝嶅簲缁撴瀯鍙樻洿鏃剁殑鏈€灏忓墠绔吋瀹规鏌?
## 6. 鏂囩尞绾跨储锛堟敞鎰忔牳瀹烇紝鏃ц〃涓儴鍒嗘潯鐩?venue/鏂规硶鏈夎锛?
- Mannocci et al. *Detection and Characterization of Coordinated Online Behavior: A Survey* (arXiv 2408.01257, 2024) 鈥?Detection/Characterization 妗嗘灦
- Luceri et al. *CIB on TikTok* (arXiv 2505.10867, 2025) 鈥?琛屼负鍨嬩俊鍙峰彲杩佺Щ銆佸唴瀹瑰瀷涓嶅彲杩佺Щ鐨勫疄璇?- Schneider, Yuan, Rizoiu *Beyond Content* (arXiv 2602.02838, 2026) 鈥?platform-agnostic 琛屼负 policy锛屾渶鎺ヨ繎鐨勫厛鍓嶅伐浣滐紙Coordination Discover 椤绘槑纭樊寮傦紝鍕垮綋鍘熷垱棣栧彂锛?- CooRTweet锛堝叡浜璞￠厤瀵癸紝宸ョ▼鍩虹嚎鏉ユ簮锛?- Cinus/Minici/Luceri/Ferrara *Exposing Cross-Platform CIB* (arXiv 2410.22716, 2024)

