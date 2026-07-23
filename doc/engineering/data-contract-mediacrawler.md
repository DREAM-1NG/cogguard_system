# CogGuard MediaCrawler 鏁版嵁濂戠害

> 浜嬩欢鏍锋湰锛歚event_id=trump_visit_2026_05_21`  
> 鏁版嵁搴擄細MongoDB `cogguard`  
> 闆嗗悎锛歚raw_posts`銆乣raw_comments`  
> 瑕嗙洊骞冲彴锛歚weibo`銆乣xhs`銆乣douyin`  
> 鐢熸垚鏃ユ湡锛?026-05-21

鏈枃妗ｅ熀浜庡綋鍓?MongoDB 涓洰鏍囦簨浠剁殑鐪熷疄鍏ュ簱鏁版嵁锛屼互鍙婁唬鐮佷腑鐨勬爣鍑嗘ā鍨嬩笌 MediaCrawler 褰掍竴鍖栭€昏緫鏁寸悊銆傛爣鍑嗘ā鍨嬪畾涔夎 `new-system/backend/app/models/post.py`锛孧ediaCrawler 瀛楁鏄犲皠瑙?`new-system/backend/app/core/crawler/social.py`銆?
## 1. 鏍囧噯鏁版嵁妯″瀷

### 1.1 StandardPost 瀛楁琛?
| 瀛楁鍚?| 绫诲瀷 | 鍚箟 | 鏉ユ簮骞冲彴瀛楁 | 鏄惁蹇呭～ | 涓嬫父鐢ㄩ€?|
|---|---|---|---|---|---|
| `platform` | `str` | CogGuard 骞冲彴鏍囪瘑 | 閲囬泦浠诲姟骞冲彴鍙傛暟锛歚weibo` / `xhs` / `douyin` | 鏄?| 璺ㄥ钩鍙扮瓫閫夈€佷簨浠跺榻愩€佺湅鏉跨粺璁°€佸崗鍚屾娴嬪垎骞冲彴鍒嗘瀽 |
| `post_id` | `str` | 骞冲彴鍐呭笘瀛?绗旇/瑙嗛 ID | weibo: `note_id`; xhs: `note_id`; douyin: `aweme_id`; 閫氱敤鍥為€€锛歚id` / `video_id` / `content_id` | 鏄?| 甯栧瓙璇︽儏銆佽瘎璁哄叧鑱斻€佸幓閲嶃€佷紶鎾浘鑺傜偣 |
| `event_id` | `str \| None` | CogGuard 浜嬩欢 ID | 瀵煎叆/棰勫鐞嗛樁娈靛啓鍏?| 褰撳墠浜嬩欢蹇呭～ | 浜嬩欢绾ф祻瑙堛€佽法骞冲彴浜嬩欢鑱氬悎銆侀闄╂姤鍛婁富閿?|
| `source_keyword` | `str \| None` | 瑙﹀彂閲囬泦鐨勫叧閿瘝 | MediaCrawler 琛屽唴 `source_keyword` 鎴栧鍏ラ樁娈佃ˉ鍏?| 寤鸿蹇呭～ | 浜嬩欢婧簮銆佸叧閿瘝杩囨护銆侀噰闆嗕换鍔¤В閲?|
| `dedupe_key` | `str \| None` | 璺ㄩ泦鍚堢ǔ瀹氬幓閲嶉敭 | 棰勫鐞嗙敓鎴愶細`{event_id}:{platform}:post:{post_id}` | 寤鸿蹇呭～ | 骞傜瓑瀵煎叆銆佸閲忓悓姝ャ€侀噸澶嶆暟鎹不鐞?|
| `content` | `str` | 甯栧瓙姝ｆ枃 | weibo: `content`; xhs: `title` + `desc`; douyin: `desc` / `title`; 閫氱敤锛歚content` / `desc` / `title` | 鏄?| 鎼滅储銆佽涔夌浉浼煎害銆佺珛鍦?鍗卞鍒嗘瀽銆佸崗鍚岃涔夎竟 |
| `author_id` | `str` | 浣滆€呭钩鍙?ID | `user_id` / `uid` / `author_id` | 鏄?| 璐﹀彿鐢诲儚銆佸崗鍚岃处鍙疯妭鐐广€佷紶鎾鑹茶瘑鍒?|
| `author_name` | `str` | 浣滆€呮樀绉?| `nickname` / `author_name` / `user_name` / `user_nickname` | 鏄?| 鍓嶇灞曠ず銆佽鎯呴〉銆佷汉宸ュ鏍?|
| `timestamp` | `datetime` | 鍙戝竷鏃堕棿 | `create_time` / `create_ts` / `time` / `publish_time` / `pub_ts` | 鏄?| 鏃堕棿绾裤€佹椂闂村悓姝ュ崗鍚岃竟銆佽秼鍔块娴?|
| `url` | `str` | 鍘熷笘 URL | weibo: `note_url`; xhs: `note_url`; douyin: `aweme_url`; 閫氱敤锛歚url` / `share_url` | 鍚?| 璺宠浆鍘熸枃銆佽瘉鎹摼銆佹姤鍛婂紩鐢?|
| `likes` | `int` | 鐐硅禐鏁?| `liked_count` / `digg_count` / `like_count` | 鍚︼紝榛樿 0 | 鐑害鎺掑簭銆佷紶鎾奖鍝嶅姏銆侀闄╁洜瀛?|
| `reposts` | `int` | 杞彂/鍒嗕韩鏁?| `shared_count` / `share_count` / `repost_count` | 鍚︼紝榛樿 0 | 浼犳挱鑼冨洿浼拌銆佹墿鏁ｅ己搴︺€侀闄╁洜瀛?|
| `comments_count` | `int` | 璇勮鏁?| `comments_count` / `comment_count` / `video_comment` | 鍚︼紝榛樿 0 | 鐑害鎺掑簭銆佽瘎璁烘爲鍏ュ彛銆佷紶鎾椿璺冨害 |
| `media_urls` | `list[str]` | 鍥剧墖銆佽棰戙€佸皝闈€侀煶棰戠瓑濯掍綋閾炬帴 | `media_urls` / `image_list` / `images` / `pictures` / `video_url` / `video_download_url` / `note_download_url` / `music_download_url` / `cover_url` / `video_cover_url` / `play_url` | 鍚︼紝榛樿绌哄垪琛?| 甯栧瓙璇︽儏銆佸叡濯掍綋鍗忓悓杈广€佸妯℃€佽瘉鎹?|
| `hashtags` | `list[str]` | 鏍囩鍒楄〃 | `hashtags` / `tag_list` / `tags` | 鍚︼紝榛樿绌哄垪琛?| 鍏辨爣绛惧崗鍚岃竟銆佽瘽棰樿仛绫汇€佷簨浠舵祻瑙堢瓫閫?|
| `author_profile` | `dict \| None` | 浣滆€呯敾鍍忓揩鐓?| `user_id`銆乣nickname`銆乣avatar`銆乣gender`銆乣profile_url`銆乣ip_location`銆乣sec_uid`銆乣user_signature`銆乣tag_list` 绛?| 寤鸿蹇呭～ | 璐﹀彿鐢诲儚銆佽鎯呴〉浣滆€呭崱鐗囥€佽嚜鍔ㄥ寲鍊惧悜璇勫垎 |
| `crawl_job_id` | `int \| None` | 閲囬泦浠诲姟 ID | Celery 閲囬泦浠诲姟鍐欏叆 | 寤鸿蹇呭～ | 浠诲姟杩借釜銆佸垹闄や换鍔℃椂娓呯悊鍏宠仈鏁版嵁 |
| `raw_data` | `dict \| None` | 鍘熷骞冲彴璁板綍淇濈湡鍓湰 | MediaCrawler JSONL 鍘熻 | 寤鸿蹇呭～ | 瀛楁杩芥函銆佸钩鍙板樊寮傝ˉ鍋裤€佸悗缁噸褰掍竴鍖?|
| `created_at` | `datetime` | 鏍囧噯妯″瀷鍒涘缓鏃堕棿 | `StandardPost` 榛樿鐢熸垚 | 鏄?| 绯荤粺瀹¤銆佸鍏ユ椂闂磋拷韪?|
| `imported_at` | `datetime` | 鏁版嵁瀵煎叆鏃堕棿 | 棰勫鐞?瀵煎叆闃舵鍐欏叆 | 褰撳墠浜嬩欢瀛樺湪 | 鏁版嵁娌荤悊銆佹壒娆″璁?|

### 1.2 StandardComment 瀛楁琛?
| 瀛楁鍚?| 绫诲瀷 | 鍚箟 | 鏉ユ簮骞冲彴瀛楁 | 鏄惁蹇呭～ | 涓嬫父鐢ㄩ€?|
|---|---|---|---|---|---|
| `platform` | `str` | CogGuard 骞冲彴鏍囪瘑 | 閲囬泦浠诲姟骞冲彴鍙傛暟 | 鏄?| 璺ㄥ钩鍙扮瓫閫夈€佽瘎璁虹粺璁°€佷紶鎾垎鏋?|
| `comment_id` | `str` | 骞冲彴鍐呰瘎璁?ID | weibo: `comment_id`; xhs: `comment_id`; douyin: `comment_id`; 閫氱敤鍥為€€锛歚cid` / `id` | 鏄?| 璇勮璇︽儏銆佽瘎璁烘爲鑺傜偣銆佸幓閲?|
| `post_id` | `str` | 鎵€灞炲笘瀛?ID | weibo/xhs: `note_id`; douyin: `aweme_id`; 閫氱敤锛歚video_id` / `post_id` / `content_id` | 鏄?| 甯栧瓙-璇勮鍏宠仈銆佽瘎璁烘爲銆佷紶鎾浘杈?|
| `event_id` | `str \| None` | CogGuard 浜嬩欢 ID | 瀵煎叆/棰勫鐞嗛樁娈靛啓鍏?| 褰撳墠浜嬩欢蹇呭～ | 浜嬩欢绾ц瘎璁烘煡璇€侀闄╄瘉鎹敹鏉?|
| `source_keyword` | `str \| None` | 瑙﹀彂閲囬泦鐨勫叧閿瘝 | MediaCrawler 琛屽唴 `source_keyword` 鎴栧鍏ラ樁娈佃ˉ鍏?| 寤鸿蹇呭～ | 浜嬩欢婧簮銆佸叧閿瘝杩囨护 |
| `dedupe_key` | `str \| None` | 绋冲畾鍘婚噸閿?| 棰勫鐞嗙敓鎴愶細`{event_id}:{platform}:comment:{comment_id}` | 寤鸿蹇呭～ | 骞傜瓑瀵煎叆銆侀噸澶嶈瘎璁烘不鐞?|
| `content` | `str` | 璇勮姝ｆ枃 | `content` / `text` | 鏄?| 璇勮璇︽儏銆佺珛鍦烘娴嬨€佸嵄瀹虫€ц瘎浼般€佽涔夎瘉鎹?|
| `author_id` | `str` | 璇勮浣滆€呭钩鍙?ID | `user_id` / `uid` / `author_id` | 鏄?| 璐﹀彿鐢诲儚銆佷簰鍔ㄧ綉缁溿€佸崗鍚屽弬涓庣粺璁?|
| `author_name` | `str` | 璇勮浣滆€呮樀绉?| `nickname` / `author_name` / `user_name` / `user_nickname` | 鏄?| 鍓嶇灞曠ず銆佷汉宸ュ鏍?|
| `timestamp` | `datetime` | 璇勮鍙戝竷鏃堕棿 | `create_time` / `time` / `publish_time` / `created_at` | 鏄?| 璇勮鏃堕棿绾裤€佷紶鎾€熷害銆佸洖澶嶉摼鎺掑簭 |
| `reply_to` | `str \| None` | 鐖惰瘎璁?ID锛涗负绌鸿〃绀轰竴绾ц瘎璁烘垨骞冲彴鏈彁渚涚埗绾?| `parent_comment_id` / `reply_to`锛屼笖浼氳繃婊ょ┖鍊笺€乣0`銆佽嚜韬?ID | 鍚?| 璇勮鏍戝睍绀恒€佹樉寮忓洖澶嶈竟銆佷紶鎾垎鏋?|
| `likes` | `int` | 璇勮鐐硅禐鏁?| `comment_like_count` / `like_count` / `liked_count` | 鍚︼紝榛樿 0 | 鐑瘎鎺掑簭銆佽鐐瑰奖鍝嶅姏 |
| `media_urls` | `list[str]` | 璇勮鍥剧墖绛夊獟浣撻摼鎺?| `media_urls` / `pictures` / 鍏朵粬濯掍綋瀛楁 | 鍚︼紝榛樿绌哄垪琛?| 璇勮璇︽儏銆佸妯℃€佽瘉鎹?|
| `sub_comment_count` | `int` | 瀛愯瘎璁烘暟閲?| `sub_comment_count` | 鍚︼紝榛樿 0 | 璇勮鏍戝姞杞芥彁绀恒€佷簰鍔ㄥ己搴?|
| `author_profile` | `dict \| None` | 璇勮浣滆€呯敾鍍忓揩鐓?| 鍚?StandardPost 鐨勪綔鑰呯敾鍍忓瓧娈甸泦鍚?| 寤鸿蹇呭～ | 璐﹀彿鐢诲儚銆佽鎯呴〉浣滆€呭崱鐗囥€佸彲鐤戣处鍙疯瘑鍒?|
| `crawl_job_id` | `int \| None` | 閲囬泦浠诲姟 ID | Celery 閲囬泦浠诲姟鍐欏叆 | 寤鸿蹇呭～ | 浠诲姟杩借釜銆佹暟鎹竻鐞?|
| `raw_data` | `dict \| None` | 鍘熷骞冲彴璇勮璁板綍淇濈湡鍓湰 | MediaCrawler JSONL 鍘熻 | 寤鸿蹇呭～ | 瀛楁杩芥函銆佽瘎璁烘爲淇銆佸悗缁噸褰掍竴鍖?|
| `created_at` | `datetime` | 鏍囧噯妯″瀷鍒涘缓鏃堕棿 | `StandardComment` 榛樿鐢熸垚 | 鏄?| 绯荤粺瀹¤ |
| `imported_at` | `datetime` | 鏁版嵁瀵煎叆鏃堕棿 | 棰勫鐞?瀵煎叆闃舵鍐欏叆 | 褰撳墠浜嬩欢瀛樺湪 | 鏁版嵁娌荤悊銆佹壒娆″璁?|

## 2. 涓夊钩鍙板瓧娈佃鐩栨儏鍐?
### 2.1 鐩爣浜嬩欢鎬讳綋瑙勬ā

| 骞冲彴 | posts 鏁伴噺 | comments 鏁伴噺 | 鎬昏褰曟暟 |
|---|---:|---:|---:|
| weibo | 165 | 2,680 | 2,845 |
| xhs | 98 | 1,905 | 2,003 |
| douyin | 31 | 10,137 | 10,168 |
| 鍚堣 | 294 | 14,722 | 15,016 |

### 2.2 瑕嗙洊鐜囩粺璁?
| 骞冲彴 | posts 鏁伴噺 | comments 鏁伴噺 | post `media_urls` 瑕嗙洊鐜?| comment `media_urls` 瑕嗙洊鐜?| post `author_profile` 瑕嗙洊鐜?| comment `author_profile` 瑕嗙洊鐜?| comment `reply_to` 闈炵┖姣斾緥 | post `raw_data` 淇濈暀 | comment `raw_data` 淇濈暀 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| weibo | 165 | 2,680 | 0.00% | 0.00% | 100.00% | 100.00% | 12.28% | 100.00% | 100.00% |
| xhs | 98 | 1,905 | 100.00% | 1.73% | 100.00% | 100.00% | 6.46% | 100.00% | 100.00% |
| douyin | 31 | 10,137 | 100.00% | 0.00% | 100.00% | 100.00% | 41.19% | 100.00% | 100.00% |

### 2.3 骞冲彴瀛楁瑕嗙洊瑙傚療

#### weibo

- 鍏ュ簱甯栧瓙鍘熷瀛楁涓昏鍖呮嫭锛歚note_id`銆乣content`銆乣create_time`銆乣create_date_time`銆乣liked_count`銆乣comments_count`銆乣shared_count`銆乣note_url`銆乣user_id`銆乣nickname`銆乣avatar`銆乣gender`銆乣profile_url`銆乣ip_location`銆乣post_details_raw`銆乣source_keyword`銆?- 鍏ュ簱璇勮鍘熷瀛楁涓昏鍖呮嫭锛歚comment_id`銆乣note_id`銆乣content`銆乣create_time`銆乣create_date_time`銆乣comment_like_count`銆乣sub_comment_count`銆乣parent_comment_id`銆乣user_id`銆乣nickname`銆乣avatar`銆乣gender`銆乣profile_url`銆乣ip_location`銆?- 褰撳墠鐩爣浜嬩欢涓?`media_urls` 瑕嗙洊鐜囦负 0锛屽師鍥犳槸寰崥鏍锋湰鐨勫獟浣撲俊鎭富瑕侀殣鍚湪姝ｆ枃鎴?`post_details_raw`锛屽綋鍓嶅綊涓€鍖栭€昏緫娌℃湁浠?`post_details_raw` 娣卞眰鎻愬彇瑙嗛/鍥剧墖閾炬帴銆?- `reply_to` 闈炵┖姣斾緥涓?12.28%锛岃鏄庡凡淇濈暀閮ㄥ垎浜岀骇璇勮鍏崇郴锛屽彲鏀拺鍒濈増璇勮鏍戯紝浣嗕笉鏄畬鏁存繁灞傞€掑綊璇勮鏍戙€?
#### xhs

- 鍏ュ簱甯栧瓙鍘熷瀛楁涓昏鍖呮嫭锛歚note_id`銆乣type`銆乣title`銆乣desc`銆乣note_url`銆乣image_list`銆乣video_url`銆乣time`銆乣liked_count`銆乣comment_count`銆乣share_count`銆乣tag_list`銆乣xsec_token`銆乣user_id`銆乣nickname`銆乣avatar`銆乣ip_location`銆?- 鍏ュ簱璇勮鍘熷瀛楁涓昏鍖呮嫭锛歚comment_id`銆乣note_id`銆乣content`銆乣create_time`銆乣like_count`銆乣sub_comment_count`銆乣parent_comment_id`銆乣pictures`銆乣user_id`銆乣nickname`銆乣avatar`銆乣ip_location`銆?- 甯栧瓙 `media_urls` 瑕嗙洊鐜囦负 100%锛屽彲鐩存帴鏀寔甯栧瓙璇︽儏椤靛獟浣撻瑙堝拰鍏卞獟浣撳崗鍚岃竟銆?- 璇勮 `media_urls` 瑕嗙洊鐜囦负 1.73%锛岃鏄庡浘鐗囪瘎璁哄皯閲忓瓨鍦紝浣嗕笉搴斾綔涓烘牳蹇冨垎鏋愪緷璧栥€?- `tag_list` 宸茶浆涓?`hashtags`锛岄€傚悎鍋氳瘽棰樼瓫閫夊拰鍏辨爣绛惧崗鍚屻€?
#### douyin

- 鍏ュ簱甯栧瓙鍘熷瀛楁涓昏鍖呮嫭锛歚aweme_id`銆乣aweme_type`銆乣title`銆乣desc`銆乣aweme_url`銆乣cover_url`銆乣video_download_url`銆乣music_download_url`銆乣note_download_url`銆乣create_time`銆乣liked_count`銆乣comment_count`銆乣share_count`銆乣user_id`銆乣nickname`銆乣avatar`銆乣sec_uid`銆乣short_user_id`銆乣user_unique_id`銆乣user_signature`銆乣ip_location`銆?- 鍏ュ簱璇勮鍘熷瀛楁涓昏鍖呮嫭锛歚comment_id`銆乣aweme_id`銆乣content`銆乣create_time`銆乣like_count`銆乣sub_comment_count`銆乣parent_comment_id`銆乣pictures`銆乣user_id`銆乣nickname`銆乣avatar`銆乣sec_uid`銆乣short_user_id`銆乣user_unique_id`銆乣user_signature`銆乣ip_location`銆?- 甯栧瓙 `media_urls` 瑕嗙洊鐜囦负 100%锛屽彲鏀拺瑙嗛璇︽儏鍜屽獟浣撹瘉鎹睍绀恒€?- `reply_to` 闈炵┖姣斾緥涓?41.19%锛岃瘎璁烘爲灞曠ず浠峰€兼渶楂樸€?- 璇勮 `media_urls` 褰撳墠涓?0锛岃瘎璁哄垎鏋愬簲浼樺厛渚濊禆鏂囨湰銆佷綔鑰呫€佹椂闂淬€佺埗璇勮鍏崇郴鍜屼簰鍔ㄩ噺銆?
## 3. 涓嬫父绯荤粺寮€鍙戝缓璁?
### 3.1 浜嬩欢鏁版嵁娴忚椤?
浼樺厛寤鸿浜嬩欢绾ф暟鎹祻瑙堥〉锛屼綔涓哄悗缁墍鏈夊垎鏋愭ā鍧楃殑鍏ュ彛銆傞〉闈㈠簲浠?`event_id` 涓轰富杩囨护鏉′欢锛屽睍绀轰笁骞冲彴甯栧瓙涓庤瘎璁烘€婚噺銆佸叧閿瘝鍒嗗竷銆佹椂闂磋寖鍥淬€佸钩鍙板垎甯冦€佸獟浣撹鐩栫巼銆佷綔鑰呯敾鍍忚鐩栫巼鍜屽師濮嬫暟鎹繚鐪熺姸鎬併€傚綋鍓嶇洰鏍囦簨浠跺凡鏈?15,016 鏉¤褰曪紝瓒充互鏀拺浜嬩欢绾у垎椤点€佺瓫閫夈€佹帓搴忓拰缁熻鍗＄墖銆?
寤鸿棣栨壒鎺ュ彛锛?
- `GET /api/v1/events/{event_id}/summary`
- `GET /api/v1/events/{event_id}/posts`
- `GET /api/v1/events/{event_id}/comments`

### 3.2 甯栧瓙璇︽儏椤?
甯栧瓙璇︽儏椤靛簲鍥寸粫 `platform + post_id` 鏌ヨ锛屽睍绀烘爣鍑嗗瓧娈点€佸師鏂囬摼鎺ャ€佹鏂囥€佸獟浣撻瑙堛€佷綔鑰呯敾鍍忋€佷簰鍔ㄦ寚鏍囥€佸叧鑱旇瘎璁恒€乣raw_data` 鎶樺彔璋冭瘯鍖恒€傚皬绾功鍜屾姈闊冲獟浣撹鐩栫巼涓?100%锛岄€傚悎浣滀负璇︽儏椤靛獟浣撻瑙堢殑棣栨壒楠岃瘉骞冲彴锛涘井鍗氳鎯呴〉闇€鍏佽濯掍綋涓虹┖銆?
寤鸿棣栨壒鎺ュ彛锛?
- `GET /api/v1/events/{event_id}/posts/{platform}/{post_id}`
- `GET /api/v1/events/{event_id}/posts/{platform}/{post_id}/comments`

### 3.3 璇勮鏍戝睍绀?
璇勮鏍戝簲浣跨敤 `post_id` 鍏宠仈甯栧瓙锛屼娇鐢?`reply_to` 杩炴帴鐖惰瘎璁恒€傜敱浜?`reply_to` 鍙湪閮ㄥ垎璇勮涓潪绌猴紝鍓嶇闇€瑕佸悓鏃舵敮鎸佷袱绉嶅舰鎬侊細

- `reply_to is null`锛氫竴绾ц瘎璁哄垪琛ㄣ€?- `reply_to` 闈炵┖锛氭寕鍒扮埗璇勮涓嬶紱鎵句笉鍒扮埗璇勮鏃跺綊鍏モ€滃绔嬪洖澶?缂哄け鐖惰妭鐐光€濆垎缁勩€?
鎶栭煶鐩爣浜嬩欢 `reply_to` 闈炵┖姣斾緥鏈€楂橈紙41.19%锛夛紝閫傚悎浣滀负璇勮鏍戦娴嬪钩鍙般€傚井鍗氬拰灏忕孩涔︿粛鑳藉睍绀轰竴绾ц瘎璁哄拰灏戦噺浜岀骇鍏崇郴銆?
### 3.4 璺ㄥ钩鍙颁簨浠跺榻?
褰撳墠浜嬩欢绾х粺涓€渚濊禆 `event_id`锛屽钩鍙板唴瀹炰綋渚濊禆 `post_id/comment_id`锛屽鍏ュ幓閲嶄緷璧?`dedupe_key`銆備笅涓€姝ラ渶瑕佽ˉ鍏呬簨浠跺榻愬眰锛?
- 浠?`event_id` 姹囨€诲骞冲彴鏁版嵁銆?- 浠?`source_keyword` 瑙ｉ噴閲囬泦鏉ユ簮銆?- 浠ユ枃鏈浉浼煎害銆佹爣绛俱€佹椂闂寸獥鍙ｃ€乁RL/濯掍綋鐩镐技搴︽瀯寤鸿法骞冲彴 claim/thread銆?- 涓洪闄╀笌鎶ュ憡妯″潡鐢熸垚鍙紩鐢ㄧ殑 `claim_id` / `thread_id`銆?
### 3.5 璐﹀彿鐢诲儚

褰撳墠 `author_profile` 鍦ㄥ笘瀛愬拰璇勮涓鐩栫巼鍧囦负 100%锛屽彲绔嬪嵆鏀拺浣滆€呭崱鐗囧拰鍩虹璐﹀彿鐢诲儚銆傚缓璁厛鍋氳交閲忕敾鍍忚仛鍚堬細

- 鎸?`platform + author_id` 鑱氬悎鍙戝笘鏁般€佽瘎璁烘暟銆佺偣璧炴€婚噺銆佹椿璺冩椂闂村垎甯冦€佸弬涓庡叧閿瘝銆?- 淇濈暀骞冲彴鐗规湁瀛楁锛氬井鍗?`gender/profile_url/ip_location`锛屽皬绾功 `tag_list/xsec_token/ip_location`锛屾姈闊?`sec_uid/user_unique_id/user_signature/ip_location`銆?- 璐﹀彿璇︽儏椤甸渶瑕佸睍绀衡€滃師濮嬬敾鍍忓瓧娈碘€濇姌鍙犲尯锛岄伩鍏嶈繃鏃╀涪澶卞钩鍙板樊寮傘€?
### 3.6 鍗忓悓妫€娴?
鐜版湁鏁版嵁宸插叿澶囧崗鍚屾娴嬫墍闇€鐨勬牳蹇冨瓧娈碉細`author_id`銆乣timestamp`銆乣content`銆乣hashtags`銆乣media_urls`銆乣post_id`銆乣platform`銆傚缓璁紑鍙戦『搴忥細

1. 鍏堣鍗忓悓妫€娴?API 鏀寔 `event_id` 杩囨护锛岄伩鍏嶅叏搴撴壂鎻忔垨鍙寜骞冲彴鍒嗘瀽銆?2. 鍦ㄥ綋鍓嶅叡浜璞″崗鍚屽熀纭€涓婂鍔犲琛屼负璇佹嵁杈癸細鏃堕棿鍚屾銆佸叡鏍囩/鍏遍摼鎺ャ€佸叡濯掍綋銆佽涔夎繎浼笺€佷紶鎾簰鍔ㄣ€?3. 瀵瑰井鍗氬獟浣撶己澶卞仛闄嶇骇锛氬井鍗氬厛鐢ㄦ枃鏈?URL/璇濋鍜屾椂闂村悓姝ワ紝寰呮繁灞傚獟浣撴彁鍙栬ˉ榻愬悗鍐嶅姞鍏ュ叡濯掍綋杈广€?4. 杈撳嚭璇佹嵁鏍锋湰鏃跺紩鐢?`raw_data` 鍜屽師甯?URL锛屼繚璇佸彲澶嶆牳銆?
### 3.7 浼犳挱鍒嗘瀽

浼犳挱鍒嗘瀽搴斾互 `event_id` 涓轰富鍏ュ彛锛岃瀺鍚堝笘瀛愭椂闂寸嚎涓庤瘎璁烘爲锛?
- 鐢?`timestamp` 鏋勫缓璺ㄥ钩鍙板彂甯冩椂闂寸嚎銆?- 鐢?`post_id -> comments` 鍜?`reply_to` 鏋勫缓鏄惧紡浜掑姩杈广€?- 鐢?`likes/reposts/comments_count/sub_comment_count` 浼拌鎵╂暎寮哄害銆?- 鐢?`source_keyword`銆乣hashtags`銆佹枃鏈浉浼煎害鑱氬悎 claim/thread銆?- 浜у嚭鍏抽敭瑙掕壊锛氳捣鐖嗚妭鐐广€佹ˉ鎺ヨ妭鐐广€佹墿鏁ｈ妭鐐广€佽瘎璁哄満楂樺奖鍝嶈妭鐐广€?
## 4. 涓庣郴缁熷姛鑳介棴鐜殑瀵归綈

绯荤粺鏂囨。瀹氫箟鐨勪富绾挎槸锛?
```text
浜嬩欢 -> 璇佹嵁 -> 鍗忓悓 -> 浼犳挱 -> 椋庨櫓 -> 澶勭疆
```

PRD 涓笁澶у姛鑳介棴鐜负锛?
1. 鍗忓悓鍙戠幇锛氬彂鐜拌法骞冲彴鍗忓悓琛屼负锛岃緭鍑哄崗鍚屽垽瀹氥€佸崗鍚岀被鍨嬨€佸崗鍚岀兢缁勫拰璇佹嵁杈广€?2. 浼犳挱鐩戞帶锛氳拷婧簮澶淬€佽寖鍥村拰瓒嬪娍锛岃緭鍑轰紶鎾浘銆佸叧閿鑹层€佹椂闂寸嚎鍜岃秼鍔块娴嬨€?3. 鎶ュ憡鐮斿垽锛氭秷璐瑰崗鍚屼笌浼犳挱缁撴灉锛岃緭鍑洪闄╄瘎鍒嗐€丏ISARM 鏄犲皠銆佹姤鍛婂拰澶勭疆寤鸿銆?
褰撳墠 `trump_visit_2026_05_21` 鐨勫叆搴撴暟鎹凡缁忚兘鏀拺鈥滀簨浠?-> 璇佹嵁鈥濈殑绗竴娈甸棴鐜細涓夊钩鍙版暟鎹粺涓€鎸傚埌鍚屼竴 `event_id`锛屽笘瀛?璇勮鍧囦繚鐣欐爣鍑嗗瓧娈典笌 `raw_data`銆傛帴涓嬫潵鐨勫伐绋嬮噸鐐瑰簲浠庘€滈噰闆嗘槸鍚﹁兘璺戔€濊浆鍒扳€滀簨浠舵暟鎹浣曡娴忚銆佸鏍搞€佸垎鏋愬拰涓嬫父娑堣垂鈥濄€?
## 5. 涓変釜鍏抽敭鎶€鏈ā鍧楃殑寮€鍙戞寚鍚?
### 5.1 Coordination Discover锛氳法骞冲彴鍗忓悓妫€娴?
鏂囨。瑕佹眰 Coordination Discover 浠庤涓哄闆嗗悎杈撳嚭鍗忓悓鍒ゅ畾銆佺被鍨嬫爣绛俱€佺兢缁勫拰璇佹嵁杈广€傝矾绾垮浘鏄剧ず鍏变韩瀵硅薄 CooRTweet MVP 宸插畬鎴愶紝浣嗗琛屼负杈规瀯寤哄拰鏄捐憲鎬х瓫鏌ヤ粛闇€鍔犲己銆?
缁撳悎褰撳墠鏁版嵁锛孋oordinationDiscover 鐨勮繎鏈熺洰鏍囧簲鏄細

- 璁╁崗鍚屾娴嬩互 `event_id` 涓鸿緭鍏ヨ竟鐣屻€?- 浣跨敤 `timestamp`銆乣author_id`銆乣content`銆乣hashtags`銆乣media_urls`銆乣reply_to` 鏋勫缓澶氳涓鸿瘉鎹€?- 杈撳嚭姣忔潯鍗忓悓杈圭殑涓昏璇佹嵁绫诲瀷鍜屽彲澶嶆牳鏍锋湰銆?- 澧炲姞鑷劧鍏辨尟涓庝汉涓哄崗鍚岀殑鏄捐憲鎬х瓫鏌ュ弬鏁般€?
### 5.2 Propagation Analysis锛氫紶鎾洃鎺т笌瓒嬪娍棰勬祴

鏂囨。瑕佹眰 Propagation Analysis 鍦ㄤ紶鎾瓙鍥惧拰鍏抽敭瑙掕壊鍩虹涓婅緭鍑鸿秼鍔块娴嬶紝骞惰ˉ榻愮珛鍦烘娴嬨€佸嵄瀹虫€ц瘎浼扮瓑淇″彿渚?Review 娑堣垂銆傝矾绾垮浘鏄剧ず浼犳挱瀛愬浘銆佹椂闂寸嚎銆佸叧閿鑹插凡瀹屾垚锛學P4-5 绔嬪満/鍗卞灏氭湭鍚姩銆?
缁撳悎褰撳墠鏁版嵁锛孭ropagationAnalysis 鐨勮繎鏈熺洰鏍囧簲鏄細

- 浠?`event_id` 鑱氬悎甯栧瓙鍜岃瘎璁烘椂闂寸嚎銆?- 浼樺厛鍒╃敤鎶栭煶杈冨畬鏁寸殑璇勮鍥炲鍏崇郴楠岃瘉璇勮鏍戝拰浜掑姩杈广€?- 灏?`likes/reposts/comments_count/sub_comment_count` 杞负浼犳挱寮哄害鐗瑰緛銆?- 浜у嚭 claim/thread 绾т紶鎾憳瑕侊紝涓烘姤鍛婄爺鍒ゆ彁渚涜緭鍏ャ€?
### 5.3 Review锛氭姤鍛婄爺鍒や笌鎶ュ憡鐢熸垚

鏂囨。瑕佹眰 Review 娑堣垂 Coordination Discover銆丳ropagationAnalysis 涓庣煡璇嗗簱锛岃緭鍑虹粨鏋勫寲鎶ュ憡銆丏ISARM 鏄犲皠鍜屽缃缓璁€傝矾绾垮浘鏄剧ず鎶ュ憡鐮斿垽 MVP 宸插畬鎴愶紝浣?LLM bridge銆丄gent+RAG 娣卞害鍒嗘瀽锛屼互鍙婇璀?鎶ュ憡涓績/澶勭疆璺熻釜浠嶅緟琛ラ綈銆?
缁撳悎褰撳墠鏁版嵁锛孯eview 鐨勮繎鏈熺洰鏍囧簲鏄細

- 鍏堝皢鎶ュ憡鐮斿垽杈撳叆浠庘€滃钩鍙扮瓫閫夆€濆崌绾т负鏄庣‘鐨?`event_id`銆?- 鎶婂崗鍚岃瘉鎹€佷紶鎾瘉鎹€佽处鍙风敾鍍忚瘉鎹粺涓€涓哄彲瀹¤ evidence pack銆?- 灏嗛闄╂姤鍛婃寔涔呭寲锛屽苟鎻愪緵鎶ュ憡璇︽儏涓庡鍑哄叆鍙ｃ€?- 鍦ㄨ鍒欒瘉鎹ǔ瀹氬悗锛屽啀鎺ュ叆 LLM bridge 鍋氳В閲婂寮猴紝鑰屼笉鏄綔涓虹涓€闃舵鏈€缁堣鍐炽€?
## 6. 鎺ㄨ崘涓嬩竴闃舵寮€鍙戠洰鏍?
鎺ㄨ崘涓嬩竴闃舵浠モ€滀簨浠舵暟鎹棴鐜?MVP鈥濅负绗竴寮€鍙戠洰鏍囷紝鑰屼笉鏄珛鍗虫繁鍏ュ崟涓畻娉曟ā鍧楋細

1. 鏂板浜嬩欢鏁版嵁 API 涓庝簨浠舵暟鎹祻瑙堥〉锛岀‘璁?`event_id` 浣滀负绯荤粺涓诲叆鍙ｃ€?2. 鏂板甯栧瓙璇︽儏涓庤瘎璁烘爲灞曠ず锛岄獙璇佹爣鍑嗗瓧娈点€佸獟浣撱€佷綔鑰呯敾鍍忓拰 `raw_data` 鍙鏍搞€?3. 鏀归€犲崗鍚屾娴嬨€佷紶鎾垎鏋愩€佹姤鍛婄爺鍒ゅ叆鍙ｏ紝浣夸笁鑰呴兘鏀寔 `event_id=trump_visit_2026_05_21`銆?4. 鍦ㄨ浜嬩欢涓婅窇閫?`浜嬩欢 -> 璇佹嵁 -> 鍗忓悓 -> 浼犳挱 -> 椋庨櫓 -> 鎶ュ憡/澶勭疆寤鸿` 鐨勬渶灏忛棴鐜€?5. 闂幆璺戦€氬悗锛屽啀鍒嗘ā鍧楀寮?Coordination Discover 澶氳涓哄崗鍚屻€丳ropagationAnalysis 绔嬪満/鍗卞涓庤秼鍔块娴嬨€丷eview 鎶ュ憡涓績鍜岄璀﹀缃€?
杩欐牱鍋氱殑鍘熷洜鏄細褰撳墠鐪熷疄鏁版嵁宸茬粡鍏ュ簱锛屼絾鐜版湁鍔熻兘鏂囨。鍜岄儴鍒?API 浠嶄互骞冲彴/鍏ㄥ簱涓轰富鍏ュ彛銆傚厛寤虹珛浜嬩欢绾ф祻瑙堝拰璇︽儏澶嶆牳鑳藉姏锛屽彲浠ヨ鍚庣画鍗忓悓銆佷紶鎾€侀闄╂ā鍧楁嫢鏈夊悓涓€浠藉彲楠岃瘉杈撳叆锛屽噺灏戠畻娉曞紑鍙戦樁娈电殑瀹氫綅鎴愭湰銆?
