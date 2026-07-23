# F-ACCT锛堟繁搴﹁处鍙风敾鍍忥級浠ｇ爜寮€鍙戦渶姹傛枃妗?
> **鍔熻兘绫诲瀷**锛氭í鍚戞敮鎾戝姛鑳斤紙supporting function锛夛紝涓嶆槸绗?4 涓叧閿妧鏈?> **涓昏鎶€鏈?*锛氶璁粌 Bot 妫€娴嬫ā鍨嬶紙Botometer / RoBERTa Twibot-22锛? 璐﹀彿绾?stance 鑱氬悎 + 瑙勫垯鍖?KOL 璇嗗埆
> **鏂囨。绫诲瀷**锛氬姛鑳界骇浠ｇ爜寮€鍙戦渶姹傦紙research / engineering 鎷嗗垎锛?> **鏈€鍚庢洿鏂?*锛?026-05-20
> **閰嶅鏂囨。**锛歔research-engineering-split.md](./research-engineering-split.md)锛堢郴缁熸€昏锛夈€乕../../aris/tech-02-propagation/REQUIREMENTS.md](../../aris/tech-02-propagation/REQUIREMENTS.md)锛堜笌 F-PROP WP4 鐨勫垎灞傚绾︼級

---

## 涓€銆佸姛鑳藉畾浣?
### 1.1 鍦?CogGuard 涓殑瑙掕壊

F-ACCT 鏄?CogGuard 涓婚摼璺殑**妯悜璇佹嵁灞?*锛岃涓夊ぇ鏍稿績鍔熻兘锛團-COORD / F-PROP / F-RISK锛?*鍏卞悓娑堣垂**锛岃嚜韬笉鐩存帴瀵瑰鍋氶闄╁垽瀹氥€?
```
                鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?                鈹?  F-ACCT 娣卞害璐﹀彿鐢诲儚锛堟湰鏂囷級  鈹?                鈹? 鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹? 鈹?                鈹? 鈹?bot detection          鈹? 鈹?                鈹? 鈹?stance aggregation     鈹? 鈹?                鈹? 鈹?KOL identification     鈹? 鈹?                鈹? 鈹?activity profiling     鈹? 鈹?                鈹? 鈹?work-rest pattern      鈹? 鈹?                鈹? 鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹? 鈹?                鈹斺攢鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹?                     鈹?       鈹?       鈹?                     鈻?       鈻?       鈻?                F-COORD   F-PROP    F-RISK
                (鍗忓悓妫€娴? (浼犳挱鐩戞帶) (鎶ュ憡鐮斿垽)
```

**鍏抽敭璁よ瘑**锛欶-ACCT **涓嶆槸绗?4 涓叧閿妧鏈?*锛屽師鍥狅細

| 鍒ゅ畾缁村害 | F-ACCT 灞炴€?|
|---|---|
| 绠楁硶鍒涙柊鎬?| 鈿狅笍 浣?鈥?bot detection / stance 鑱氬悎閮芥槸宸ヤ笟鐣屾垚鐔熸柟娉?|
| 鏄惁鐙珛鍙紨绀?| 鉂?鍚?鈥?鍗曚釜璐﹀彿鐨?bot_score 娌℃湁绔炶禌鍙欎簨浠峰€?|
| 鏄惁琚鍔熻兘娑堣垂 | 鉁?鏄?鈥?Coordination Discover 鐢?bot_prob 杩囨护銆丳ropagationAnalysis 鐢?stance 鍒嗗竷銆丷eview 鐢?KOL 鏍囪瘑 |
| 涓庝笂娓?analysis capability 鍏崇郴 | 骞宠 + 鏀拺锛堥潪渚濊禆锛?|
| 璁烘枃 ROI | 浣?鈥?鍗曞啓涓嶅鍙戣〃锛屼綔涓?ablation 瀛愰」鏇村悎閫?|

**瀹氫綅缁撹**锛?0% engineering + 10% research 杈圭晫锛堜粎 stance 鑱氬悎鐨勭粺璁″缓妯?+ bot detection 妯″瀷閫夋嫨闇€璋冨弬锛夈€?
### 1.2 杈撳叆涓庤緭鍑?
**杈撳叆**锛?
- MongoDB `raw_posts` / `raw_comments`锛堣处鍙风殑鍏ㄩ儴鍙戞枃涓庝簰鍔級
- 鍗曚釜鐢ㄦ埛涓婚〉閲囬泦缁撴灉锛堜富椤?URL銆佹樀绉般€佺畝浠嬨€佺矇涓?鍏虫敞/鑾疯禐銆佽璇併€両P 灞炲湴銆佷富椤靛唴瀹规祦锛?- 璐﹀彿鍏冩暟鎹紙绮変笣鏁?/ 璁よ瘉绫诲瀷 / 娉ㄥ唽鏃堕棿 / 澶村儚 URL / IP 褰掑睘锛?- F-PROP WP4 鐨?*甯栫骇 stance 杈撳嚭**锛堢敤浜庤处鍙风骇鑱氬悎锛?
**杈撳嚭**锛?
```python
account_profile = {
    "account_id": str,
    "platform": str,

    # 鑷姩鍖栨娴嬶紙鏂板锛?    "bot": {
        "score": float,            # 0-1锛岃秺楂樿秺鍍?bot
        "model": str,              # "botometer-v4" | "twibot22-roberta" | "rule-based"
        "confidence": float,
        "explanation": [str],      # 瑙﹀彂鐨勫叧閿壒寰?    },

    # 绔嬪満鑱氬悎锛堟柊澧烇紝娑堣垂 F-PROP WP4锛?    "stance": {
        "distribution": {"support": float, "against": float, "neutral": float,
                         "sarcasm": float, "questioning": float, "ambiguous": float},
        "extremity_index": float,  # 鏋佸寲绋嬪害 0-1
        "consistency": float,      # 绔嬪満涓€鑷存€э紙澶氬笘涔嬮棿锛?        "sample_size": int,        # 鍙備笌鑱氬悎鐨勫笘鏁?    },

    # KOL 璇嗗埆锛堟柊澧烇級
    "kol": {
        "is_kol": bool,
        "tier": str,               # "head" | "mid" | "tail" | "none"
        "influence_score": float,  # 0-100
        "reasons": [str],          # 瑙﹀彂鏍囩
    },

    # 琛屼负鐢诲儚锛堟棫 account_profiler.py 淇濈暀锛?    "activity": {
        "post_frequency": float,
        "interval_cv": float,      # 鍙戞枃闂撮殧鍙樺紓绯绘暟
        "work_rest_pattern": [float],   # 24h 鐩存柟鍥?        "interaction_breakdown": {"like": int, "share": int, "comment": int},
        "content_diversity": float,
    },

    # 鏃?automation_score锛堜笌 bot.score 鍏卞瓨锛屼究浜庡洖褰掞級
    "automation_score": float,     # 0-100
}
```

### 1.3 瀵规爣绯荤粺

| 瀵规爣 | 绫诲瀷 | 涓?F-ACCT 鍏崇郴 |
|---|---|---|
| Botometer X (Indiana U) | 瀛︽湳 + 鍏紑 API | bot detection 鐨勫伐涓氬熀绾?|
| Twibot-22 (RoBERTa) | 瀛︽湳寮€婧愭ā鍨?| bot detection 鐨勯璁粌妯″瀷閫夐」 |
| Pegabot / BotSentinel | 宸ヤ笟鐣?| KOL 璇嗗埆鐨勪骇鍝佸弬鑰?|
| 寰崥 / 鎶栭煶鍘熺敓璁よ瘉 | 骞冲彴鍘熺敓 | KOL 绛夌骇鐨勪簨瀹炲弬鐓?|

---

## 浜屻€佸瓙鍔熻兘鎷嗚В

### 2.1 瀛愬姛鑳芥竻鍗曪紙5 涓級

| # | 瀛愬姛鑳?| 鍋氫粈涔?| 杈撳叆 | 杈撳嚭 | 钀界偣鏂囦欢 | 鐘舵€?|
|---|---|---|---|---|---|---|
| F-ACCT-1 | Bot detection | 鍖哄垎鐪熶汉 / 鏈哄櫒浜?/ 鍗婅嚜鍔?| 璐﹀彿鍏冩暟鎹?+ 鍘嗗彶鍙戞枃 | `bot.score / model / explanation` | `core/account/bot_detector.py`锛堟柊澧烇級 | 鉂?鏈紑濮?|
| F-ACCT-2 | 璐﹀彿绾?stance 鑱氬悎 | 鑱氬悎澶氬笘绔嬪満涓鸿处鍙风骇鍒嗗竷 | F-PROP WP4 甯栫骇 stance | `stance.distribution / extremity / consistency` | `core/account/stance_aggregator.py`锛堟柊澧烇級 | 鉂?渚濊禆 Propagation Analysis WP4 |
| F-ACCT-3 | KOL 璇嗗埆 | 澶撮儴 / 涓儴 / 灏鹃儴鍒嗙骇 | 绮変笣鏁?+ 璁よ瘉 + 浜掑姩閲?+ F-PROP 褰卞搷鍔?| `kol.tier / influence_score / reasons` | `core/account/kol_identifier.py`锛堟柊澧烇級 | 鉂?鏈紑濮?|
| F-ACCT-4 | 琛屼负鐢诲儚 | 鍙戞枃棰戠巼 / 浣滄伅 / 鍐呭澶氭牱鎬?| 璐﹀彿鍘嗗彶鍙戞枃 | `activity.*` | `core/account_profiler.py` (185)锛堝凡鏈夛紝闇€杩佸叆 `core/account/`锛?| 鉁?MVP |
| F-ACCT-5 | 鑷姩鍖栧€惧悜璇勫垎锛堟棫锛?| 澶氱淮缁煎悎 0-100 璇勫垎 | F-ACCT-4 杈撳嚭 | `automation_score` | `core/account_profiler.py`锛堝凡鏈夛級 | 鉁?MVP |
| F-ACCT-6 | 鍗曠敤鎴蜂富椤甸噰闆嗕笌鍐呭宸℃ | 鎸変富椤甸摼鎺?鐢ㄦ埛 ID 鎶撳彇涓婚〉鍏冩暟鎹拰鍏ㄩ儴鍐呭锛屽苟瀵瑰唴瀹瑰仛椋庨櫓/绔嬪満/妯℃澘鍖栨娴?| MediaCrawler 鐢ㄦ埛涓婚〉鑳藉姏 + raw_posts/raw_comments | `homepage / posts / content_checks` | `services/account_service.py` + crawler 鎵╁睍 | 鉂?鏈紑濮?|

### 2.2 鐩綍閲嶇粍锛堝缓璁級

褰撳墠 `core/account_profiler.py` 鏄崟鏂囦欢銆傛柊澧?3 涓瓙鍔熻兘鍚庯紝寤鸿鎻愬崌涓哄寘锛?
```
new-system/backend/app/core/account/                  鈫?鏂板缓鍖?鈹溾攢鈹€ __init__.py                                       鈫?閲嶆柊瀵煎嚭鏃?API
鈹溾攢鈹€ activity_profiler.py    鈫?杩佽嚜 core/account_profiler.py锛?85 琛岋級
鈹溾攢鈹€ bot_detector.py         鈫?鏂板锛團-ACCT-1锛寏250 琛岋級
鈹溾攢鈹€ stance_aggregator.py    鈫?鏂板锛團-ACCT-2锛寏150 琛岋級
鈹溾攢鈹€ kol_identifier.py       鈫?鏂板锛團-ACCT-3锛寏200 琛岋級
鈹斺攢鈹€ config/
    鈹溾攢鈹€ bot_features.yaml   鈫?瑙勫垯妯″瀷鐗瑰緛娓呭崟锛坒allback锛?    鈹斺攢鈹€ kol_thresholds.yaml 鈫?KOL 鍒嗙骇闃堝€?```

**鍚戝悗鍏煎**锛歚core/account_profiler.py` 淇濈暀涓?thin shim锛?
```python
# core/account_profiler.py锛堜繚鐣欙紝shim锛?from .account.activity_profiler import *  # 鍘?API 鍏ㄩ儴 re-export
```

---

## 涓夈€佷富瑕佹妧鏈紙research / engineering 杈圭晫锛?
### 3.1 F-ACCT-1 Bot Detection锛氭贩鍚堟灦鏋勶紙鐢ㄦ埛閫夊畾棰勮缁冭矾绾匡級

**鏋舵瀯**锛堝弻灞傦級锛?
```
璐﹀彿 鈫?[Layer 1: 瑙勫垯缁熻鐗瑰緛]
       鍙戞枃闂撮殧CV / 浣滄伅瑙勫緥鎬?/ 璺ㄥ钩鍙伴噸璐寸巼 / 澶村儚缂哄け / 鍚嶅瓧妯″紡 / ...
       杈撳嚭 rule_score 鈭?[0, 1]
           鈹?           鈻?       [Layer 2: 棰勮缁冩ā鍨嬫帹鏂璢
       Botometer X API锛堥閫夛紝闇€澶栫綉锛?         鎴?twibot22-roberta锛堟湰鍦?transformers锛孋PU 鍙嬪ソ锛?       杈撳嚭 ml_score 鈭?[0, 1]
           鈹?           鈻?       [Fusion]
       final_score = 0.4 路 rule_score + 0.6 路 ml_score
           鈹?           鈻?       {score, model="botometer-v4" | "twibot22-roberta" | "rule-based",
        confidence, explanation: top-5 features}
```

**闄嶇骇閾?*锛?
1. **棣栭€?*锛欱otometer X API锛堥渶 `RAPIDAPI_KEY` 鐜鍙橀噺锛?2. **娆￠€?*锛氭湰鍦?`twibot22-roberta` 妯″瀷鎺ㄦ柇锛圚uggingFace transformers锛?3. **闄嶇骇**锛氱函瑙勫垯缁熻锛堜笌鐜版湁 `automation_score` 鍚屾簮锛?
**research 閮ㄥ垎**锛?
- 棰勮缁冩ā鍨嬮€夋嫨锛圔otometer v4 vs twibot22-roberta vs Cresci-2017锛?- 涓枃绀句氦濯掍綋涓婄殑 zero-shot 鍑嗙‘鐜囷紙杩欎簺妯″瀷涓昏鍦ㄨ嫳鏂?Twitter 璁粌锛?- 瑙勫垯缁熻鐗瑰緛娓呭崟锛?0-15 涓級+ 鍚勭壒寰佹潈閲?- Fusion 鏉冮噸锛?.4 / 0.6 鏄惁鍚堢悊锛?
**engineering 閮ㄥ垎**锛?
- API 瀹㈡埛绔?+ 閲嶈瘯 + 闄愭祦 + 缂撳瓨锛圧edis锛?- HuggingFace 妯″瀷鍔犺浇锛坙azy + LRU cache锛?- 瑙勫垯缁熻瀹炵幇锛坧andas 鍚戦噺鍖栵級
- 閰嶇疆鏂囦欢 `bot_features.yaml` 鍔犺浇
- 鍗曞厓娴嬭瘯 + mock fallback

### 3.2 F-ACCT-2 璐﹀彿绾?Stance 鑱氬悎锛堜笌 Propagation Analysis WP4 鍒嗗眰濂戠害锛?
**鑱岃矗杈圭晫**锛堢敤鎴烽€夊畾鐨?鎷嗗眰"鏂规锛夛細

| 灞傜骇 | 璋佽礋璐?| 杈撳叆 | 杈撳嚭 |
|---|---|---|---|
| **甯栫骇 stance** | F-PROP WP4 `stance_detector.py` | 鍗曞笘鏂囨湰 | `{stance: support/against/.../ambiguous, confidence}` |
| **璐﹀彿绾?stance 鑱氬悎** | **F-ACCT-2 `stance_aggregator.py`**锛堟湰鏂囷級 | 璐﹀彿鎵€鏈夊笘鐨勫笘绾?stance 鍒楄〃 | 璐﹀彿绾?6 缁村垎甯?+ 鏋佸寲鎸囨暟 + 涓€鑷存€?|

**鑱氬悎绠楁硶**锛?
```python
def aggregate(post_stances: list[PostStance]) -> AccountStance:
    """
    post_stances: [{stance: 'support', confidence: 0.82}, ...]
    """
    # 鍔犳潈棰戠巼锛堢敤缃俊搴﹀姞鏉冿級
    distribution = weighted_frequency(post_stances)

    # 鏋佸寲鎸囨暟锛歴upport 涓?against 鐨勮緝澶у€?    extremity = max(distribution["support"], distribution["against"])

    # 涓€鑷存€э細1 - normalized entropy
    consistency = 1.0 - shannon_entropy(distribution) / log(6)

    return {
        "distribution": distribution,
        "extremity_index": extremity,
        "consistency": consistency,
        "sample_size": len(post_stances),
    }
```

**research 閮ㄥ垎**锛?
- 鍔犳潈棰戠巼 vs 绠€鍗曢鐜囷紙鏄惁鐢ㄧ疆淇″害鍔犳潈锛?- 鏋佸寲鎸囨暟瀹氫箟锛坢ax vs L2 璺濈 from uniform vs Wasserstein from uniform锛?- 涓€鑷存€ф寚鏍囬€夋嫨锛坋ntropy / variance / Gini锛?- 灏忔牱鏈紙< 5 甯栵級鐨勫鐞?
**engineering 閮ㄥ垎**锛?
- 璋冪敤 F-PROP API 鑾峰彇甯栫骇 stance
- 鍔犳潈棰戠巼 / 鐔?/ Wasserstein 绛夊叕寮忓疄鐜?- 缂撳瓨锛堣处鍙?+ 鏃堕棿绐?鈫?鑱氬悎缁撴灉锛?- 涓?F-PROP WP4 鐨勬帴鍙ｅ榻?
### 3.3 F-ACCT-3 KOL 璇嗗埆锛堢函 engineering锛?
**瑙勫垯鍖?*锛堟棤 research锛夛細

```yaml
# config/kol_thresholds.yaml
head:
  followers_min: 1000000
  verified_required: true
  influence_score_min: 80
mid:
  followers_min: 100000
  followers_max: 999999
  influence_score_min: 50
tail:
  followers_min: 10000
  followers_max: 99999
  influence_score_min: 30
none:
  # fallback
```

**influence_score 鍏紡**锛?
```
influence_score = 0.3 路 normalized(followers)
                + 0.2 路 normalized(avg_likes_per_post)
                + 0.2 路 verified_factor    # 钃漋/榛刅/濯掍綋璁よ瘉
                + 0.2 路 post_frequency_factor
                + 0.1 路 network_centrality  # 鐢?F-COORD 鎻愪緵
```

**research 閮ㄥ垎**锛氭棤锛堣鍒欏叏閮ㄥ彲閰嶇疆锛?**engineering 閮ㄥ垎**锛氬叏閮?
### 3.4 F-ACCT-4 / F-ACCT-5 宸叉湁锛岃縼鍏ユ柊鍖?
宸插疄鐜颁簬 `core/account_profiler.py`锛?85 琛岋級锛屾湰鏈熶粎鍋?*鐩綍杩佺Щ + 鍖?import 璺緞璋冩暣**锛屾棤鍔熻兘鏀瑰姩銆?
### 3.5 F-ACCT-6 鍗曠敤鎴蜂富椤甸噰闆嗕笌鍐呭宸℃

**鑱岃矗杈圭晫**锛氭湰瀛愬姛鑳借仛鐒?鎸変富椤甸摼鎺?鐢ㄦ埛 ID 鎶撳彇 + 鍐呭妫€娴嬭惤搴?锛屼笉閲嶅瀹炵幇鐖櫕鈥斺€?*澶嶇敤 MediaCrawler 宸叉湁鐨?creator/profile 妯″紡**銆?
**鏋舵瀯**锛堜笁娈垫祦姘寸嚎锛夛細

```
璇锋眰锛坧rofile_url 鎴?platform+account_id锛?  鈹?  鈹溾攢鈹€鈫?[Stage 1: 涓婚〉閲囬泦] homepage_collector.py
  鈹?    璋冪敤 MediaCrawler creator 妯″紡 鈫?涓婚〉鍏冩暟鎹?+ 涓婚〉鍐呭娴侊紙鍏ㄩ噺鍙戞枃/瑙嗛锛?  鈹?    钀藉簱锛歳aw_posts锛堝凡鏈夛級+ account_homepage锛堟柊澧烇級
  鈹?  鈹溾攢鈹€鈫?[Stage 2: 鍐呭宸℃锛坈ontent_checks锛塢 content_checker.py
  鈹?    瀵硅鐢ㄦ埛鐨勫叏閮ㄥ彂鏂囪皟鐢細
  鈹?      鈥?椋庨櫓妫€娴?  鈫?澶嶇敤 F-RISK harm_assessor 鎴?Propagation Analysis WP5锛堟寜甯栫骇鑱氬悎锛?  鈹?      鈥?绔嬪満妫€娴?  鈫?澶嶇敤 F-PROP WP4 stance_detector锛堟寜甯栫骇锛? F-ACCT-2 璐﹀彿绾ц仛鍚?  鈹?      鈥?妯℃澘鍖栨娴?鈫?澶嶇敤 F-COORD channels.py 鐨勮涔夐噸澶?/ hashtag 妯℃澘妫€娴?  鈹?    杈撳嚭 per-post checks + 璐﹀彿绾ц仛鍚堟寚鏍?  鈹?  鈹斺攢鈹€鈫?[Stage 3: 璇︽儏椤靛搷搴旂粍瑁匽 account_service.py
        homepage 鍏冩暟鎹?+ posts[] + per-post checks[] + 璐﹀彿绾ц仛鍚?```

**鍏抽敭浜х墿 schema**锛?
```python
homepage_response = {
    "account_id": str, "platform": str,
    "homepage": {
        "profile_url": str, "nickname": str, "bio": str,
        "followers": int, "following": int, "likes_total": int,
        "verified": bool, "verified_type": str,
        "ip_location": str, "registered_at": str,
        "avatar_url": str,
        "collected_at": str,
    },
    "posts": [   # 璇ヨ处鍙峰叏閮ㄥ彂鏂囷紙鎸夋椂闂村€掑簭锛?        {"post_id": ..., "created_at": ..., "content": ..., "media_urls": [...],
         "engagement": {"like": ..., "share": ..., "comment": ...}}
    ],
    "content_checks": [  # 涓?posts 涓€涓€瀵瑰簲
        {
            "post_id": ...,
            "harm": {"score": float, "dimensions": {...}},   # 澶嶇敤 Propagation Analysis WP5
            "stance": {"label": str, "confidence": float},   # 澶嶇敤 Propagation Analysis WP4
            "template": {"is_template": bool, "template_id": str | None,
                         "duplicate_count": int}             # 澶嶇敤 F-COORD 閫氶亾
        }
    ],
    "aggregated": {
        "harm_score_avg": float, "harm_score_max": float,
        "stance_distribution": {...},                         # F-ACCT-2 璐﹀彿绾?        "template_post_ratio": float,
    }
}
```

**闄嶇骇绛栫暐**锛?
1. **棣栭€?*锛歁ediaCrawler creator 妯″紡锛坵eibo / douyin / xhs锛屽凡鏀寔锛?2. **娆￠€?*锛氬綋骞冲彴涓嶆敮鎸?creator 妯″紡锛堝鏂伴椈绫伙級鏃讹紝閫€鍖栦负鎼滅储寮忛噰闆嗭紙MediaCrawler 鐨?keyword 妯″紡 + author filter锛?3. **鏈€浣庨檷绾?*锛氫粎杩斿洖 MongoDB 宸叉湁鐨?raw_posts锛堜笉瑙﹀彂鏂扮埇铏級锛屽姞娉?`data_freshness="cached_only"`

**research 閮ㄥ垎**锛氭棤锛堢埇铏鐢?+ 妫€娴嬪鐢紝涓嶅紩鍏ユ柊绠楁硶锛?
**engineering 閮ㄥ垎**锛?
- MediaCrawler creator 妯″紡灏佽 + 澶辫触閲嶈瘯 + 棰戠巼鎺у埗锛堥伩鍏嶈处鍙烽鎺э級
- 鍐呭宸℃鐨勫苟鍙戞壒澶勭悊锛堜竴涓处鍙峰彲鑳芥湁鏁扮櫨鏉″彂鏂囷級
- 妯℃澘鍖栨娴嬶細F-COORD `channels.py` 鐨勮涔?hashtag 妯℃澘鎶藉彇闇€瑕?batch 鍗曡处鍙锋ā寮忥紙涓嶅悓浜庣兢浣撳崗鍚屾ā寮忥級
- account_homepage 琛?/ `services.collect_homepage()` 缂栨帓
- 鍓嶇璐︽埛璇︽儏椤碉紙涓婚〉鍏冩暟鎹?+ 鍐呭娴?+ 宸℃缁撴灉涓夋爮锛?
**涓庣幇鏈?crawler 妯″潡鐨勫叧绯?*锛?
- 涓嶅湪 `core/crawler/` 涓嬫柊澧炵埇铏紝鑰屾槸鍦?`core/account/homepage_collector.py` 涓?*璋冪敤** `core/crawler/social.py` 鐨勭幇鏈夊瓙杩涚▼鍏ュ彛锛堝甫 `mode=creator` 鍙傛暟锛?- 鑻?`core/crawler/social.py` 褰撳墠涓嶆敮鎸?`mode=creator`锛岄渶鍦?`social.py` 涓墿灞曚竴涓弬鏁帮紙灞炰簬 crawler 妯″潡鐨?engineering 宸ヤ綔锛屽綊鍏?F-ACCT-6 鑼冨洿锛?
---

## 鍥涖€丄PI 璁捐

### 4.1 鏂板绔偣

```http
GET  /api/v1/accounts/profile/{account_id}        # 鑾峰彇瀹屾暣鐢诲儚
POST /api/v1/accounts/batch-profile                # 鎵归噺鐢诲儚
GET  /api/v1/accounts/{account_id}/bot              # 浠?bot 瀛愰」
GET  /api/v1/accounts/{account_id}/stance           # 浠?stance 鑱氬悎
GET  /api/v1/accounts/{account_id}/kol              # 浠?KOL 瀛愰」
POST /api/v1/accounts/homepage/collect              # 閲囬泦鍗曚釜鐢ㄦ埛涓婚〉鍐呭
GET  /api/v1/accounts/{account_id}/homepage          # 鏌ョ湅涓婚〉鍏冩暟鎹笌涓婚〉鍐呭娴?GET  /api/v1/accounts/{account_id}/contents          # 鏌ョ湅璇ョ敤鎴峰叏閮ㄥ彂鏂囧強鍐呭妫€娴嬬粨鏋?```

### 4.2 鏈嶅姟灞?
```
new-system/backend/app/services/account_service.py锛堝凡鏈夛紝鎵╁埌 ~150 琛岋級
  鈹溾攢 get_profile(account_id) 鈫?璋冪敤 4 涓瓙妯″潡鑱氬悎
  鈹溾攢 get_bot(account_id) 鈫?bot_detector.detect()
  鈹溾攢 get_stance(account_id, time_range) 鈫?鎷?F-PROP WP4 + stance_aggregator
  鈹溾攢 get_kol(account_id) 鈫?kol_identifier.identify()
  鈹溾攢 collect_homepage(profile_url | account_id, platform) 鈫?璋冪敤 MediaCrawler 鐢ㄦ埛涓婚〉鑳藉姏
  鈹斺攢 get_account_contents(account_id, platform, event_id) 鈫?杩斿洖鍏ㄩ儴鍙戞枃涓庡唴瀹规娴嬬粨鏋?```

### 4.3 鏁版嵁搴撴寔涔呭寲

鏂板 MySQL 琛紙寰?alembic 杩佺Щ锛夛細

```sql
CREATE TABLE account_profile_cache (
    id INT PRIMARY KEY AUTO_INCREMENT,
    account_id VARCHAR(64) NOT NULL,
    platform VARCHAR(32) NOT NULL,
    profile_json JSON,
    computed_at DATETIME,
    expires_at DATETIME,
    INDEX (account_id, platform)
);

-- F-ACCT-6 涓婚〉鍏冩暟鎹紙涓庡彂鏂囨祦鍒嗙锛屽彂鏂囨祦浠嶅啓 raw_posts锛?CREATE TABLE account_homepage (
    id INT PRIMARY KEY AUTO_INCREMENT,
    account_id VARCHAR(64) NOT NULL,
    platform VARCHAR(32) NOT NULL,
    profile_url VARCHAR(512),
    nickname VARCHAR(128),
    bio TEXT,
    followers INT, following INT, likes_total BIGINT,
    verified BOOLEAN, verified_type VARCHAR(32),
    ip_location VARCHAR(64),
    registered_at DATETIME,
    avatar_url VARCHAR(512),
    collected_at DATETIME,
    UNIQUE KEY (platform, account_id)
);
```

**缂撳瓨绛栫暐**锛?
- bot.score锛? 澶╄繃鏈燂紙璐﹀彿鐗瑰緛鎱㈠彉鍖栵級
- stance锛? 灏忔椂杩囨湡锛堜笌浜嬩欢绐楀彛瀵归綈锛?- kol锛?0 澶╄繃鏈?- activity锛? 澶╄繃鏈?
---

## 浜斻€佺幇鏈変唬鐮佽祫浜?vs 寰呮柊澧?
### 5.1 宸叉湁

| 鏂囦欢 | 琛屾暟 | 鐘舵€?| 鏈湡澶勭悊 |
|---|---|---|---|
| `core/account_profiler.py` | 185 | 鉁?MVP | 杩佸叆 `core/account/activity_profiler.py`锛屼繚鐣?shim |
| `services/account_service.py` | 43 | 鈿狅笍 闆忓舰 | 鎵╁埌 ~150 琛?|
| `api/v1/accounts.py` | 30 | 鈿狅笍 闆忓舰 | 鏂板 4 涓鐐?|
| `frontend/src/views/accounts/index.vue` | 鈥?| 鉁?MVP锛堣瘎鍒?+ 鎺掑簭锛?| 琛?bot / stance / KOL 涓夋灞曠ず |

### 5.2 寰呮柊澧?
| 鏂囦欢 | 宸ヤ綔閲?| 鏍囩 |
|---|---|---|
| `core/account/__init__.py` | 15 min | engineering |
| `core/account/bot_detector.py` | 5-7 h | research-杈圭晫锛堟ā鍨嬮€?+ 璋冨弬锛?|
| `core/account/stance_aggregator.py` | 2-3 h | research-杈圭晫锛堣仛鍚堝叕寮忥級+ engineering锛堝疄鐜帮級 |
| `core/account/kol_identifier.py` | 2-3 h | engineering锛堢函瑙勫垯锛?|
| `core/account/homepage_collector.py` | 4-5 h | engineering锛堝皝瑁?MediaCrawler creator 妯″紡 + 閲嶈瘯 + 闄嶇骇锛?|
| `core/account/content_checker.py` | 3-4 h | engineering锛堢紪鎺?Propagation Analysis WP4/WP5 + F-COORD 妯℃澘妫€娴嬬殑鎵瑰鐞嗭級 |
| `core/account/config/bot_features.yaml` | 1-2 h锛堝惈鐗瑰緛璁鸿瘉锛?| engineering |
| `core/account/config/kol_thresholds.yaml` | 30 min | engineering |
| `core/crawler/social.py` 鎵╁睍 `mode=creator` 鍙傛暟 | 2-3 h | engineering锛堜緷璧?MediaCrawler creator 瀛愬懡浠ゅ皝瑁咃級 |
| `models/account_homepage.py` | 30 min | engineering |
| `alembic/versions/xxx_add_account_profile_cache.py` | 30 min | engineering |
| `alembic/versions/xxx_add_account_homepage.py` | 30 min | engineering |
| `tests/test_account_profile.py` | 3-4 h | engineering |
| `tests/test_homepage_collector.py` | 2 h | engineering |
| `frontend/views/accounts/components/BotPanel.vue` | 2 h | engineering |
| `frontend/views/accounts/components/StancePanel.vue` | 2 h | engineering |
| `frontend/views/accounts/components/KOLPanel.vue` | 1.5 h | engineering |
| `frontend/views/accounts/detail/index.vue` | 6-8 h | engineering锛堣处鎴疯鎯呴〉锛氫富椤?+ 鍐呭娴?+ 宸℃涓夋爮锛?|

### 5.3 閰嶇疆 / 渚濊禆

- `pyproject.toml`锛氳ˉ `transformers`銆乣torch`锛圕PU 鐗堬級渚濊禆锛堝閫?twibot22-roberta 鏈湴璺嚎锛?- `pyproject.toml`锛氳ˉ `httpx` 璋冪敤 Botometer API锛堝凡鏈夛級
- `.env.example`锛氳ˉ `RAPIDAPI_KEY`銆乣BOT_DETECTOR_PROVIDER`锛坄botometer` / `twibot22` / `rule`锛夈€乣BOT_DETECTOR_MOCK`

---

## 鍏€乺esearch vs engineering 鎷嗗垎杈圭晫锛團-ACCT 瑙嗚锛?
### 6.1 research 浠诲姟锛堟湰鍦板疄楠岋紝灏戦噺锛?
| # | 浠诲姟 | 闃诲 / 鏁版嵁鏉ユ簮 | 楠岃瘉鏂瑰紡 |
|---|---|---|---|
| R1 | Bot detection 棰勮缁冩ā鍨嬮€夋嫨 | 涓枃绀句氦濯掍綋 zero-shot 鍑嗙‘鐜囨湭鐭?| 鍦?100 鏉′汉宸ユ爣娉ㄥ井鍗氳处鍙蜂笂瀵规瘮 Botometer / twibot22-roberta / 瑙勫垯涓夌 |
| R2 | Fusion 鏉冮噸锛堣鍒?vs ML锛?| 榛樿 0.4 / 0.6 鏈獙璇?| 缃戞牸鎼滅储 + 鏍囨敞闆?F1 |
| R3 | 瑙勫垯鐗瑰緛娓呭崟 | 10-15 涓壒寰佹湭瀹?| 涓?`automation_score` 鏃㈡湁鐗瑰緛瀵规瘮 + 鏂囩尞缁艰堪 |
| R4 | Stance 鑱氬悎鏂规硶 | 鍔犳潈 vs 绠€鍗曢鐜?/ 鏋佸寲瀹氫箟 | 鍦ㄦ爣娉ㄨ处鍙蜂笂浜哄伐璇勪及 6 缁村垎甯冧竴鑷存€?|
| R5 | KOL 闃堝€兼牎鍑?| 榛樿闃堝€硷紙100w/10w/1w锛夐渶骞冲彴鐗瑰紓鍖?| 鎸夊钩鍙帮紙weibo/douyin/xhs锛夊悇鑷牎鍑?|

### 6.2 engineering 浠诲姟锛圕laude Code锛?
| 浼樺厛绾?| # | 浠诲姟 | 宸ヤ綔閲?|
|---|---|---|---|
| P0 | E1 | 鐩綍杩佺Щ锛歚core/account_profiler.py` 鈫?`core/account/activity_profiler.py` + shim | 1 h |
| P0 | E2 | 琛?`pyproject.toml` 渚濊禆锛坱ransformers / torch CPU锛? `.env` 鐜鍙橀噺 | 30 min |
| P0 | E3 | alembic 杩佺Щ `account_profile_cache` 琛?| 30 min |
| P1 | E4 | `bot_detector.py` 鍙屽眰瀹炵幇 + 3 璺檷绾?+ mock | 5-7 h |
| P1 | E5 | `kol_identifier.py` 瑙勫垯鍖?+ 閰嶇疆鍔犺浇 | 2-3 h |
| P1 | E6 | `account_service.py` 鎵╁睍 4 涓柊鏂规硶 | 2 h |
| P1 | E7 | `api/v1/accounts.py` 鏂板 4 涓鐐?| 2 h |
| P1 | E8 | 鍓嶇 3 涓?Panel 缁勪欢 + 璺敱 | 5-6 h |
| P1 | E11 | F-ACCT-6 涓婚〉閲囬泦锛歚homepage_collector.py` + `core/crawler/social.py` 鎵╁睍 `mode=creator` | 6-8 h |
| P1 | E12 | F-ACCT-6 鍐呭宸℃锛歚content_checker.py` 缂栨帓 Propagation Analysis WP4/WP5 + 妯℃澘妫€娴嬫壒澶勭悊 | 3-4 h |
| P1 | E13 | F-ACCT-6 alembic 杩佺Щ `account_homepage` 琛?+ ORM 妯″瀷 | 1 h |
| P1 | E14 | F-ACCT-6 API 3 绔偣锛歚/homepage/collect` / `/homepage` / `/contents` | 2 h |
| P1 | E15 | F-ACCT-6 鍓嶇璐︽埛璇︽儏椤碉紙涓婚〉 + 鍐呭娴?+ 宸℃涓夋爮锛?| 6-8 h |
| P2 | E9 | `stance_aggregator.py`锛堜緷璧?F-PROP WP4 瀹屾垚锛?| 2-3 h |
| P2 | E10 | 缂撳瓨灞傦紙Redis锛? TTL 绛栫暐 | 2 h |

**鍏抽敭渚濊禆**锛?
- E9 闃诲浜?**F-PROP WP4 stance_detector.py**锛圥ropagationAnalysis 鏈惎鍔級
- E4 闃诲浜?**R1 妯″瀷閫夋嫨鍐崇瓥**锛堝缓璁厛鐢ㄨ鍒欒矾寰勮窇閫?engineering锛屾ā鍨嬭矾寰勪綔涓?R1 瀹屾垚鍚庡垏鎹級
- E11 闃诲浜?**MediaCrawler creator 瀛愬懡浠ょ殑鍙敤鎬х‘璁?*锛堝凡鐭?weibo / douyin / xhs 鏀寔锛岄渶鍦?social.py 鎺ュ叆锛?- E12 闃诲浜?**Propagation Analysis WP4 / WP5 / F-COORD 閫氶亾妯℃澘妫€娴?*鈥斺€旇嫢涓婃父鏈畬鎴愶紝content_checker 鍚敤 mock fallback锛堜粎缁欒鍒欏寲缁撴灉锛?
### 6.3 杈圭晫 case 澶勭悊

| Case | 褰掑睘 | 澶囨敞 |
|---|---|---|
| Bot 瑙勫垯鐗瑰緛娓呭崟 | research锛堝厛瀹氾級鈫?engineering锛堝疄鐜帮級 | 鍏堝湪 `bot_features.yaml` 涓互榛樿鍊艰捣姝?|
| Bot 妯″瀷閫夋嫨 | research锛圧1锛?| engineering 瀹炵幇鎸?3 璺檷绾?妗嗘灦鍏堣锛屾ā鍨嬭矾寰勫彲鍦?R1 瀹屾垚鍚庢帴 |
| Stance 鑱氬悎鍏紡 | research锛圧4锛?| engineering 鐢ㄥ姞鏉冮鐜囬粯璁よ捣姝?|

---

## 涓冦€佸叧閿璁″喅绛栦笌寮€鏀鹃棶棰?
### 7.1 鍏抽敭鍐崇瓥

1. **F-ACCT 鏄敮鎾戝姛鑳借€岄潪绗?4 涓?analysis capability**
   - 鐞嗙敱锛氱畻娉曞垱鏂版€т綆锛屾棤鐙珛绔炶禌鍙欎簨锛岃澶氬姛鑳芥秷璐?   - 褰卞搷锛氭枃妗ｆ斁 `doc/engineering/` 鑰岄潪鏂板缓 `aris/tech-04/`
   - 璇勫鍙ｅ緞锛氬湪绯荤粺鎬昏涓槑纭?涓夊ぇ鏍稿績鍔熻兘 + F-ACCT 妯悜鏀拺"

2. **Stance 鎷嗗眰锛欶-PROP=甯栫骇 / F-ACCT=璐﹀彿绾ц仛鍚?*
   - 鐞嗙敱锛氶伩鍏嶅弻杞ㄥ疄鐜帮紝澶嶇敤 Propagation Analysis WP4 绠楁硶鎴愭灉
   - 褰卞搷锛欶-ACCT-2 闃诲浜?Propagation Analysis WP4 瀹屾垚
   - 鏇夸唬鏂规锛氬厛鍦?F-ACCT 鍐呭仛"杞婚噺鍙ョ骇 stance"浣滀负 fallback锛堝鏋?Propagation Analysis WP4 杩涘害钀藉悗锛夛紝浣嗕粛浠?Propagation Analysis 杈撳嚭涓烘渶缁堟潵婧?
3. **Bot detection 璧伴璁粌妯″瀷璺嚎**
   - 鐞嗙敱锛氱敤鎴烽€夊畾锛屽噯纭巼楂樹簬绾鍒?   - 褰卞搷锛氶渶琛?transformers / torch 渚濊禆锛屾垨淇濈暀 Botometer API
   - 闄嶇骇锛欰PI 涓嶅彲鐢?+ 妯″瀷鏈姞杞芥椂閫€鍒拌鍒欒矾寰勶紝涓庣幇鏈?`automation_score` 鍚屾簮

4. **KOL 璇嗗埆淇濇寔瑙勫垯鍖?*
   - 鐞嗙敱锛氬晢涓氬钩鍙伴兘鐢ㄧ矇涓濇暟 + 璁よ瘉浣滀负鍒嗙骇锛岃鍒欏彲瑙ｉ噴
   - 褰卞搷锛氭棤 research 宸ヤ綔閲?   - 椋庨櫓锛氳法骞冲彴闃堝€奸渶鍚勮嚜鏍″噯

5. **鐩綍浠庡崟鏂囦欢鎻愬崌涓哄寘**
   - 鐞嗙敱锛氫粠 1 涓瓙鍔熻兘鎵╁埌 5 涓紝闇€瑕佹竻鏅板懡鍚嶇┖闂?   - 褰卞搷锛氱幇鏈?`core/account_profiler.py` 淇濈暀涓?shim锛屾棫 import 涓嶅彉

6. **F-ACCT-6 澶嶇敤 MediaCrawler锛屼笉鏂板鐖櫕**
   - 鐞嗙敱锛歁ediaCrawler 宸叉敮鎸?weibo / douyin / xhs 鐨?creator 妯″紡锛岄噸鏂伴€犺疆鎴愭湰楂?   - 褰卞搷锛氬湪 `core/crawler/social.py` 鎵╁睍 `mode=creator` 鍙傛暟锛宍homepage_collector.py` 閫氳繃璇ュ叆鍙ｈ皟鐢?   - 椋庨櫓锛氳嫢 MediaCrawler 鍚庣画 creator 妯″紡鏈?breaking change锛岄渶瑕?social.py 閫傞厤

7. **F-ACCT-6 鍐呭宸℃鍏ㄩ儴澶嶇敤涓婃父绠楁硶锛堜笉閲嶆柊瀹炵幇锛?*
   - 鐞嗙敱锛氶闄╂娴嬪鐢?Propagation Analysis WP5 / 绔嬪満澶嶇敤 Propagation Analysis WP4 / 妯℃澘鍖栧鐢?F-COORD 閫氶亾
   - 褰卞搷锛欶-ACCT-6 浠呭仛缂栨帓 + 鎵瑰鐞嗭紝涓嶆秹鍙婃柊绠楁硶 鈫?research = 0
   - 闄嶇骇锛氳嫢涓婃父鏈畬鎴愶紙鐗瑰埆鏄?Propagation Analysis WP4/5锛夛紝content_checker 鐢?mock fallback锛堜粎缁欒鍒欏寲缁撴灉锛夛紝骞跺湪鍝嶅簲涓槑纭?`data_completeness="partial"`

### 7.2 寮€鏀鹃棶棰?
1. **Bot 妯″瀷鍦ㄤ腑鏂囩ぞ浜ゅ獟浣撶殑 zero-shot 鎬ц兘**
   - 闃诲锛歊1 瀹為獙鏈仛
   - 缂撹В锛氳捣姝ラ樁娈电敤瑙勫垯璺緞锛屾ā鍨嬭矾寰勪綔涓哄彲閫?
2. **Stance 鑱氬悎鐨勫皬鏍锋湰闂**
   - 闃诲锛氳处鍙峰湪浜嬩欢绐楀彛鍐呭彲鑳藉彧鍙?1-2 甯?   - 缂撹В锛氭墿灞曠獥鍙ｏ紙浜嬩欢澶?7 澶╁唴鐨勭浉鍏冲笘锛? `sample_size < 5` 鏍囪浣庣疆淇″害

3. **缂撳瓨澶辨晥涓庝竴鑷存€?*
   - 闂锛歜ot.score 7 澶?cache 鏈熼棿锛岃处鍙峰彲鑳借浆涓烘椿璺?   - 缂撹В锛氬彂鏂囬鐜囩獊鍙樻椂涓诲姩澶辨晥锛坵ebhook 鎴栧畾鏃舵壂鎻忥級

4. **璺ㄥ钩鍙拌处鍙峰悓涓€鎬?*
   - 闂锛氬悓涓€鐢ㄦ埛鍦?weibo / douyin / xhs 鐨勭敾鍍忎簰涓嶆墦閫?   - 缂撹В锛氭湰鏈熶笉鍋氳法骞冲彴瀵归綈锛圡2 閿欎綅椤瑰凡寤跺悗锛夛紝鐢?`(platform, account_id)` 鍞竴閿?
5. **闅愮涓庡悎瑙?*
   - 闂锛歜ot 璇勫垎鍙兘甯︽瑙嗘晥搴旓紙璇垽鐪熶汉涓?bot锛?   - 缂撹В锛氭墍鏈夎瘎鍒嗗甫 `explanation` 瀛楁锛涘墠绔樉绀?绠楁硶鍒ゅ畾"鑰岄潪"浜嬪疄鏍囩"

---

## 鍏€佸鍏朵粬鍔熻兘鐨勬帴鍙ｅ绾?
### 8.1 F-ACCT 鈫?F-COORD

```python
# F-COORD 娑堣垂 F-ACCT 鐢ㄤ簬杩囨护 / 鍔犳潈
bot_filter = client.get_bot_scores(account_ids=[...])
# 鐢ㄦ硶 1锛氬湪 PSL 璁＄畻鍓嶈繃婊ゆ帀楂?bot_score 璐﹀彿锛堝幓闄ゅ櫔澹帮級
# 鐢ㄦ硶 2锛氭妸 bot_score 浣滀负 edge_score 鍔犳潈鍥犲瓙
```

### 8.2 F-ACCT 鈫?F-PROP

```python
# F-PROP 娑堣垂 F-ACCT 鐢ㄤ簬 KOL 淇″彿 + 鑷姩鍖栧€惧悜
account_profiles = client.get_batch_profiles(account_ids=[...])
# 鐢ㄦ硶 1锛歵rend_predictor.py 鐨勪簨浠惰瘎鍒嗗悜閲?e 涓姞鍏?kol_ratio
# 鐢ㄦ硶 2锛歜urst 鏄惁琚?KOL 鎺ㄥ姩浣滀负 amplification 浣撳埗鐨勫己淇″彿
```

### 8.3 F-ACCT 鈫?F-RISK

```python
# F-RISK 娑堣垂 F-ACCT 鐢ㄤ簬椋庨櫓鍥犲瓙
profiles = client.get_batch_profiles(account_ids=coord_group_members)
# 鐢ㄦ硶 1锛歟vidence_builder 璁＄畻 group 鐨?bot_ratio
# 鐢ㄦ硶 2锛歞s_fusion 鐨?mass(manipulation) 涓?bot_ratio 姝ｇ浉鍏?```

### 8.4 F-ACCT 鈫?F-PROP WP4锛堝弽鍚戜緷璧栵級

```python
# F-ACCT-2 stance_aggregator 璋冪敤 F-PROP 甯栫骇 stance
post_stances = client.get_post_stances(
    account_id=..., time_range=...)
# 杩斿洖 [{post_id, stance, confidence}, ...]
```

**濂戠害瑕佹眰**锛欶-PROP WP4 蹇呴』鏆撮湶 `GET /api/v1/propagation/stance/by-account?account_id=...` 绔偣銆?
### 8.5 F-ACCT-6 鈫?涓婃父绠楁硶妯″潡锛堟í鍚戠紪鎺掓秷璐癸級

F-ACCT-6 鍐呭宸℃涓嶉噸鏂板疄鐜扮畻娉曪紝鑰屾槸鎸夊笘鎵瑰鐞嗚皟鐢ㄤ笂娓革細

```python
# content_checker.py
for post in account_posts:
    harm = harm_assessor.score(post.content, post.metadata)        # 澶嶇敤 Propagation Analysis WP5
    stance = stance_detector.detect(post.content)                  # 澶嶇敤 Propagation Analysis WP4
    template = template_detector.check(post, account_corpus)       # 澶嶇敤 F-COORD channels.py
    yield {post_id: post.id, harm, stance, template}
```

**濂戠害瑕佹眰**锛?
- Propagation Analysis WP5 `harm_assessor.score(text, metadata) -> {score, dimensions}` 蹇呴』鏆撮湶涓哄彲鍗曞笘璋冪敤鐨勭函鍑芥暟
- Propagation Analysis WP4 `stance_detector.detect(text) -> {label, confidence}` 鍚屾牱
- F-COORD `channels.py` 闇€鎻愪緵 `template_detector.check(post, corpus) -> {is_template, template_id, duplicate_count}` 瀛愭帴鍙ｏ紙鍗曡处鍙疯鏂欐ā鏉挎娊鍙栵級

**闄嶇骇绛栫暐**锛氫笂娓哥己澶辨椂杩斿洖 `null` 瀛楁骞舵爣 `data_completeness="partial"`锛屽墠绔敤鍗犱綅绗︽覆鏌撱€?
---

## 涔濄€佸紩鐢?
| 绫诲埆 | 璺緞 | 鐢ㄩ€?|
|---|---|---|
| 绯荤粺鎬昏 | [research-engineering-split.md](./research-engineering-split.md) | 鍔犲叆 F-ACCT 妯悜鏀拺鍔熻兘鍚庣殑鎬诲浘 |
| F-PROP 鏂囨。 | [../../aris/tech-02-propagation/REQUIREMENTS.md](../../aris/tech-02-propagation/REQUIREMENTS.md) | WP4 甯栫骇 stance 瀹炵幇缁嗚妭 |
| F-COORD 鏂囨。 | [../../aris/tech-01-coordination/REQUIREMENTS.md](../../aris/tech-01-coordination/REQUIREMENTS.md) | 鍗忓悓妫€娴嬪 bot_score 鐨勬秷璐?|
| F-RISK 鏂囨。 | [../../aris/tech-03-risk/REQUIREMENTS.md](../../aris/tech-03-risk/REQUIREMENTS.md) | 鎶ュ憡鐮斿垽瀵硅处鍙风敾鍍忕殑娑堣垂 |
| 鐜版湁浠ｇ爜 | `new-system/backend/app/core/account_profiler.py` | 185 琛?MVP锛屽緟杩佸叆鏂板寘 |
| 鐜版湁鏈嶅姟灞?| `new-system/backend/app/services/account_service.py` | 43 琛岄洀褰紝寰呮墿 |
| 鐜版湁 API | `new-system/backend/app/api/v1/accounts.py` | 30 琛岋紝寰呮墿 |
| 鐜版湁鍓嶇 | `new-system/frontend/src/views/accounts/index.vue` | 宸叉湁璇勫垎椤?|

---

## 鍗併€佸悗缁姩浣?
**绗竴鍛紙engineering 涓诲锛孋laude Code锛?*锛?
1. E1锛氱洰褰曡縼绉?+ shim 鈫?1 h
2. E2 + E3锛氫緷璧?+ alembic锛堝惈 E13 account_homepage 琛級 鈫?1.5 h
3. E4锛歚bot_detector.py` 妗嗘灦 + 瑙勫垯璺緞 + mock锛堟ā鍨嬭矾寰勫崰浣嶏級 鈫?4 h
4. E5锛歚kol_identifier.py` 瑙勫垯鍖?+ 閰嶇疆鍔犺浇 鈫?3 h
5. E11锛欶-ACCT-6 `homepage_collector.py` + `social.py` 鎵╁睍 `mode=creator` 鈫?6-8 h
6. E12锛欶-ACCT-6 `content_checker.py` 缂栨帓锛堜笂娓哥己澶辨椂 mock fallback锛?鈫?3-4 h
7. E6 + E7 + E14锛氭湇鍔″眰 + API锛堝惈 F-ACCT-6 涓変釜鏂扮鐐癸級 鈫?6 h
8. E8 + E15锛氬墠绔?3 Panel + 璐︽埛璇︽儏椤?鈫?11-14 h

**绗簩鍛紙research锛屾湰鍦板疄楠岋級**锛?
1. R1锛欱ot 妯″瀷閫夋嫨瀹為獙锛?00 鏉℃爣娉ㄨ处鍙蜂笂瀵规瘮 3 璺級 鈫?3 d
2. R3锛氳鍒欑壒寰佹竻鍗曡璇?+ 涓?`automation_score` 鏃㈡湁鐗瑰緛瀵规瘮 鈫?2 d
3. R5锛欿OL 闃堝€煎钩鍙版牎鍑嗭紙weibo / douyin / xhs 鍚?50 涓爣娉ㄨ处鍙凤級 鈫?2 d

**绗笁鍛紙璺ㄥ姛鑳借仈璋冿級**锛?
1. E9锛歚stance_aggregator.py`锛堜緷璧?Propagation Analysis WP4锛?鈫?3 h
2. E10锛歊edis 缂撳瓨灞?+ TTL 鈫?2 h
3. R2 + R4锛欶usion 鏉冮噸 + 鑱氬悎鍏紡璋冧紭 鈫?2 d
4. F-ACCT 鈫?F-COORD / F-PROP / F-RISK 鎺ュ彛鑱旇皟
5. F-ACCT-6 鍐呭宸℃浠?mock fallback 鍒囨崲鍒扮湡瀹炰笂娓革紙渚濊禆 Propagation Analysis WP4/5 + F-COORD 妯℃澘妫€娴嬶級

**鍏抽敭閲岀▼纰?*锛?
- 鍛ㄦ湯 1锛欶-ACCT MVP锛坆ot 瑙勫垯璺緞 + KOL + 鏃?activity + **F-ACCT-6 涓婚〉閲囬泦 + 璐︽埛璇︽儏椤?*锛夌鍒扮璺戦€?- 鍛ㄦ湯 2锛歜ot 妯″瀷璺緞鎺ュ叆 + R1 鏁版嵁缁撹 + F-ACCT-6 鍐呭宸℃ mock 鍏ㄥ瓧娈佃緭鍑?- 鍛ㄦ湯 3锛歴tance 鑱氬悎涓婄嚎锛堜緷璧?Propagation Analysis WP4锛? 鍏ㄩ摼璺仈璋?+ F-ACCT-6 鍒囨崲鍒扮湡瀹炵畻娉?
