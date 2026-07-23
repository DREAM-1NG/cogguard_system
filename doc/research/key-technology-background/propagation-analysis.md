# 鍏抽敭鎶€鏈簩锛氫紶鎾洃鎺?
> **鐢ㄩ€?*锛氬畾涔?Propagation Analysis 鐨勭爺绌堕棶棰樸€佸綋鍓嶅伐绋嬭惤鐐广€佺爺绌剁洰鏍囥€佸疄鐜版柟鍚戝拰楠岃瘉鏂瑰紡銆? 
> **鍙椾紬**锛歅ropagationAnalysis 鐮旂┒瀹炵幇鑰呫€佷紶鎾洃鎺фā鍧楃淮鎶よ€呫€佺瓟杈╂潗鏂欑紪鍐欒€呫€? 
> **缁存姢瑙勫垯**锛氬彧鍐欏叧閿妧鏈儗鏅笌鐮旂┒鏂规锛涗骇鍝佹帴鍙ｅ拰浠诲姟鐘舵€佹斁鍏ュ伐绋嬫枃妗ｃ€?
> 鏂瑰悜鏇存柊锛?026-06-23锛夛細Propagation Analysis 涓诲姛鑳芥敹鏁涗负 **瑙勬ā棰勬祴 + 瑙掕壊瀹氫綅 + 涓嬩竴璺抽娴?*銆備紶鎾椂闂寸嚎銆佽瘉鎹摼銆佽寖鍥翠及璁°€佺珛鍦?鍗卞/鎯呮劅绾跨储銆佸奖鍝嶅姏鎸囨暟鍜屽墠绔彲瑙嗗寲鍧囦负 auxiliary銆傛柟娉曞眰涓嶇粦瀹?CascadeSwitch銆丠yperIDP 鎴栦换浣曞崟涓€妯″瀷锛屽厑璁告牴鎹暟鎹潯浠堕€夋嫨杞婚噺鍚彂寮忋€佷紶缁熸ā鍨嬨€佸浘妯″瀷銆佸灏哄害鎵╂暎妯″瀷鎴栫粍鍚堟柟妗堛€?
## 1. 闂瀹氫箟

Propagation Analysis 瑕佸洖绛旂殑鏍稿績闂鏄細**涓€涓紶鎾簨浠舵帴涓嬫潵浼氭墿鏁ｅ埌澶氬ぇ锛屽叧閿崗鍚岀敤鎴峰湪浼犳挱涓壆婕斾粈涔堣鑹诧紝涓嬩竴姝ュ彲鑳戒紶鎾埌鍝噷銆?*

- **瑙勬ā棰勬祴**锛氱粰瀹氭棭鏈熻娴嬬獥鍙?`[0, t_obs]`锛岄娴嬫湭鏉?`t_pred` 鎴栨渶缁堟椂鍒荤殑浼犳挱瑙勬ā銆佹柟鍚戝拰鍙€夌疆淇″害銆?- **瑙掕壊瀹氫綅**锛氬宸茬粡鍙備笌浼犳挱涓斿凡琚?Coordination Discover 鍒ゅ畾涓哄崗鍚岀殑鐢ㄦ埛锛岃瘑鍒捣鐖嗐€佹ˉ鎺ャ€佹墿鏁ｃ€佹斁澶х瓑瑙掕壊锛屽苟缁欏嚭鍥剧粨鏋勬垨璇佹嵁閾句緷鎹€?- **涓嬩竴璺抽娴?*锛氬湪涓嶄娇鐢ㄦ湭鏉ョ湡瀹炶妭鐐规垨鐪熷疄杈圭殑鏉′欢涓嬶紝棰勬祴鏈潵绐楀彛鍐呮渶鍙兘琚縺娲荤殑鐢ㄦ埛鎴栦紶鎾竟銆?- **杈呭姪鑳藉姏**锛氫紶鎾瓙鍥俱€佹椂闂寸嚎銆佹簮澶磋拷婧€佽瘉鎹摼銆佽寖鍥翠及璁°€佸唴瀹圭嚎绱㈠拰鍓嶇鍙鍖栵紝涓轰笁椤逛富鍔熻兘鎻愪緵瑙ｉ噴鍜屽睍绀烘敮鎾戙€?
涓ユ牸鍖哄垎涓ょ被璺緞鑳藉姏锛?
- **璺緞鍥炴函 / 璇佹嵁杩芥函**锛氬湪宸茶娴嬩紶鎾浘涓婅В閲婅繃鍘诲彂鐢熶簡浠€涔堬紝褰撳墠宸叉湁瀹炵幇鍩虹銆?- **涓嬩竴璺?/ 璺緞棰勬祴**锛氬湪瑙傛祴绐楀彛缁撴潫鏃堕娴嬫湭鏉ヤ細鍙戠敓浠€涔堬紝褰撳墠浠嶉渶琛ラ綈鏃犳硠婕忓€欓€夌敓鎴愬拰鎺掑簭鍗忚銆?
## 2. 褰撳墠浠ｇ爜鍩虹嚎

褰撳墠浠ｇ爜钀界偣锛?
- `system/backend/app/core/propagation_legacy.py`锛氫紶鎾瓙鍥俱€佸叧閿鑹层€佽瘉鎹摼銆佸叧閿矾寰勫洖婧€?- `system/backend/app/core/propagation/`锛氭椂搴忕壒寰併€佷簨浠朵笂涓嬫枃銆佷綋鍒舵ā鍨嬨€佽秼鍔块娴嬬瓑瑙勬ā棰勬祴鍩虹瀹炵幇銆?- `system/backend/app/services/propagation_service.py`
- `system/backend/app/api/v1/propagation.py`

褰撳墠宸插疄鐜版垨宸叉湁鍩虹锛?
- 浼犳挱鍥炬瀯寤恒€佹椂闂寸嚎銆佸叧閿鑹层€佽瘉鎹摼銆佸叧閿矾寰勫洖婧€?- 瑙勬ā/瓒嬪娍棰勬祴鐩稿叧鐗瑰緛鍜岃交閲忛娴嬫祦绋嬨€?- 鍓嶇浼犳挱鐩戞帶椤电殑閮ㄥ垎灞曠ず鑳藉姏銆?
褰撳墠闇€瑕佽ˉ榻愶細

- 瑙勬ā棰勬祴鍦ㄥ叕寮€鏁版嵁闆嗕笂鐨勫熀鍑嗛獙璇佸拰涓?baseline 鐨勫姣斻€?- 瑙掕壊瀹氫綅涓?Coordination Discover 鍗忓悓鐢ㄦ埛闆嗗悎鐨勬樉寮忚仈鍔ㄣ€?- 涓嬩竴璺抽娴嬬殑鍊欓€夐泦鏋勯€犮€佹帓搴忔ā鍨嬪拰鏃犳湭鏉ユ硠婕忚瘎浼板崗璁€?- 杈呭姪鑳藉姏涓庝富鍔熻兘鐨勮竟鐣岃鏄庯紝閬垮厤鎶婂唴瀹瑰垎鏋愭垨鍓嶇灞曠ず鍐欐垚涓诲姛鑳芥湰浣撱€?
## 3. 鏂规硶绌洪棿

Propagation Analysis 涓嶉璁惧敮涓€鎶€鏈矾绾裤€傚彲閫夋柟娉曞寘鎷細

- **瑙勬ā棰勬祴**锛氶殢鏈烘．鏋椼€佺粺璁″鎺ㄣ€丠awkes/鐐硅繃绋嬨€丆ascadeSwitch銆丆asFlow銆丆asFT銆丆onCat銆丆asDO銆丠yperIDP銆丮INDS銆丗OREST 绛夈€?- **瑙掕壊瀹氫綅**锛歞egree銆乥etweenness銆丳ageRank銆佺粨鏋勬礊銆佺ぞ鍖烘ˉ鎺ャ€佷紶鎾矾寰勮瘉鎹€佸崗鍚岀粍鏉′欢鍖栬鑹茶鍒欐垨瀛︿範妯″瀷銆?- **涓嬩竴璺抽娴?*锛氶€昏緫鍥炲綊鎺掑簭銆乀opo-LSTM銆丏eepInf銆丗OREST銆丮INDS銆丠yperIDP銆乀GAT銆乀GN銆丆AW銆丏yGFormer銆乀GSL 绛夈€?
宸ョ▼钀藉湴鍙互鍒嗛樁娈垫帹杩涳細鍏堜繚璇佸惎鍙戝紡鍜屼紶缁?baseline 鍙窇锛屽啀閫愭鎺ュ叆鏇村己妯″瀷銆傛柟娉曞垱鏂扮┖闂村寘鎷絾涓嶉檺浜庡崗鍚岀敤鎴锋潯浠跺寲棰勬祴銆佸灏哄害鑱斿悎寤烘ā銆佽瘉鎹摼鍙В閲婅鑹插畾浣嶃€佷綆璧勬簮鏁版嵁涓嬬殑涓嬩竴璺冲€欓€夌敓鎴愩€?
## 4. 鎺ㄨ崘楠岃瘉鏂瑰紡

- 鐢?`mock_weibo` 楠岃瘉鎺ュ彛銆佸墠绔拰璇佹嵁閾惧睍绀轰笉鍥炲綊銆?- 鐢ㄥ叕寮€浼犳挱鏍戞垨绾ц仈鏁版嵁楠岃瘉瑙勬ā棰勬祴鍜屼笅涓€璺抽娴嬨€?- 鐢?Coordination Discover 杈撳嚭鐨勫崗鍚岀兢缁勯獙璇佽鑹插畾浣嶈兘鍚︽寜鍗忓悓鐢ㄦ埛杩囨护鍜岃В閲娿€?- 姣忛」棰勬祴浠诲姟閮芥姤鍛婅娴嬬獥鍙ｃ€侀娴嬬獥鍙ｃ€佹暟鎹垝鍒嗘柟寮忓拰鏄惁瀛樺湪鏈潵娉勬紡銆?
## 5. 鍙傝€冩枃鐚嚎绱?
- `HyperIDP: Customizing Temporal Hypergraph Neural Networks for Multi-Scale Information Diffusion Prediction` (COLING 2025)
- `Enhancing Multi-Scale Diffusion Prediction via Sequential Hypergraphs and Adversarial Learning` (AAAI 2024)
- `FOREST: Multi-scale Information Diffusion Prediction with Reinforced Recurrent Networks` (IJCAI 2019)
- `DeepCas: An End-to-end Predictor of Information Cascades` (WWW 2017)
- `DeepHawkes: Bridging the Gap between Prediction and Understanding of Information Cascades` (CIKM 2017)
- `Topological Recurrent Neural Network for Diffusion Prediction` (ICDM 2017)
- `Temporal Graph Networks for Deep Learning on Dynamic Graphs` (2020)
- `Provenance for Online Information Diffusion` (2018)
- `Rumor Detection on Social Media with Bi-Directional Graph Convolutional Networks` (AAAI 2020)

