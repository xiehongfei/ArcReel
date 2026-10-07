---
id: text/drama_script_plan
category: text
title: 剧情演绎脚本规划
description: >-
  把本集源文拆为结构化分镜内容：分镜边界、出场资产、视觉改编描述、逐字口播 utterances 与原文锚 source_text，
  定稿后由提示词编写只补视觉层。小说是改编：画外音按语境判断产出，场景切换由模型判断；
  成品剧本是提取：台词与画外音逐字照搬，保留作者场次与事件顺序，场次内按动作和时长拆镜。
  字段、枚举与必填项由 response_schema 强制，正文只讲怎么写好每个字段的内容。
  输出语言主句两种源文共用，只把例外从句按源文类型分开：资产引用与说话人须逐字等于登记名，
  翻译会与已登记资产失配；剧本额外逐字保留台词正文。
  时长拆成三条：档位按画面选、口播下界防止选到念不完台词的短档、单集目标决定拆多少个分镜；
  口播下界是单向的，只防过短，不因台词删减内容。群演不进出场角色只在候选清单处讲一次。
stage: script_plan
invoked_by:
  kind: agent_tool
  name: generate_script_plan
applies_to:
  content_mode:
  - drama
  generation_mode:
  - storyboard
  source_kind:
  - novel
  - screenplay
output_schema: lib.script.script_models:DramaNormalizedScript
slots:
  source_kind: 源文类型
  target_language: 输出语言，取项目源语言
  project_overview: 项目概述，键齐全的对象 {synopsis, genre, theme, world_setting}；缺值传 null
  style: 项目画风
  assets: 已登记资产，对象 {characters, scenes, props}，每项是 [{name, aliases, appearance}] 列表（尖括号已中和；衍生写作「本体/衍生」）
  character_names: 可引用的角色名，衍生写作「本体/衍生」
  scene_names: 可引用的场景名
  prop_names: 可引用的道具名
  novel_text: 本集源文
  episode: 集号
  durations: 视频模型支持的秒数档位
  max_duration: 最长档位秒数
  default_duration: 单个分镜的默认秒数；未设置为空
  speech_rate: 口播语速（每秒阅读单位数）
  speech_unit: 阅读单位量词（字或词）
  episode_target_duration: 单集目标时长秒数；未设置为空
  episode_outline: 本集大纲（title、story_beats、hook、next_episode_teaser）；未规划为空
  next_episode_outline: 下集大纲，形状同本集大纲；未规划为空
  instructions: 附加指令；未提供为空
protected: false
---
{{ variant("text/drama_script_plan/task", source_kind) }}

**输出语言**：自然语言字符串值必须使用 {{ target_language }}；JSON 键名 / 枚举值保持英文。{{ variant("text/drama_script_plan/language_rule", source_kind) }}
**结构约束**：字段 / 枚举 / 必填项由 response_schema 强制；本提示只解释**如何写好每个字段的内容**。

{{ partial("shared/pacing/drama") }}

## 项目信息

<overview>
{{ project_overview.synopsis or "" }}

题材类型：{{ project_overview.genre or "" }}
核心主题：{{ project_overview.theme or "" }}
世界观设定：{{ project_overview.world_setting or "" }}
</overview>

<style>
{{ style }}
</style>

{{ partial("shared/lists/asset_registry_blocks") }}

## 源文

<{{ source_kind }}>
{{ novel_text }}
</{{ source_kind }}>

{% if episode_outline %}
<episode_outline>
本集大纲（分集规划设计，剧本内容应覆盖全部故事节点）：
{% if episode_outline.title %}
本集标题：{{ episode_outline.title }}
{% endif %}
{{ partial("shared/lists/episode_outline_lines", outline=episode_outline) }}
</episode_outline>

{% if episode_outline.hook or episode_outline.next_episode_teaser %}
末场（最后一个或几个分镜）的画面与对白须实际呈现集尾钩子的戏剧内容，让悬念定格在画面上；有下集预告语时，用结尾画面或对白自然引出，不要生硬插入「下集预告」字样的旁白。

{% endif %}
{% endif %}
{% if next_episode_outline %}
<next_episode_outline>
下集大纲（仅用于设计本集结尾的衔接，不要把下集情节提前写进本集）：
{% if next_episode_outline.title %}
下集标题：{{ next_episode_outline.title }}
{% endif %}
{{ partial("shared/lists/episode_outline_lines", outline=next_episode_outline) }}
</next_episode_outline>

{% endif %}
# 叙事与连续性检查

拆镜前通读本集源文与上下集衔接信息，先在内部梳理以下内容，再写入既有字段；不要输出分析过程或增加 JSON 字段。

- **因果链**：确认本集的目标、障碍、人物选择、行动、可见结果和下一步。每次尝试都要交代做法及成败原因，成功前呈现导致成功的关键改变，不能只宣布问题已经解决。
- **观众可知的信息**：只凭画面和 utterances，观众应能理解人物为什么行动、为什么转场、结果意味着什么。source_text 只是原文锚，不会自动成为旁白；影响选择和结果的心理活动不能仅留在原文锚中，也不能用无明确含义的表情代替。
- **时空与物品状态**：内部记录每镜的地点、时间、人物位置、视线与运动方向，以及关键物品的身份、持有人、位置和完好状态。同类物品的不同实例须在 scene_description 中区分，引用字段仍使用候选登记名；不得把留在上一地点的物品无说明地带到新地点。
- **镜头承接**：每镜明确开始状态、一个主要事件和结束状态，下一镜继承结果。递交、拾取、进出场等决定理解的衔接要可见；同一动作跨镜时从上一镜终点继续，不得重复起手、投出、落地等已完成动作。时间省略、回忆、投影和地点变化须有可辨认的画面依据，不能只靠 segment_break 标记。
- **本集收束**：在集尾钩子之前交代本集已经完成的局部目标或明确的失败结果，以及仍待解决的问题。长线目标可以留到后续集数，但不得用突然出现的新危机替代本集结果；结尾状态须能接上下集开场。
{{ variant("text/drama_script_plan/continuity_rule", source_kind) }}

# 字段写作指引

把源文拆为有序分镜，逐条产出结构化分镜内容。当前正在生成第 {{ episode }} 集。

## 基础字段

- **scene_id**：`E{{ episode }}S{两位序号}` 格式（如 E{{ episode }}S01），按分镜顺序递增，不得用其他集号前缀。
- **duration_seconds**：
  - 档位：{% if default_duration %}从支持的秒数档位（{{ durations }}）中按画面内容选择：默认 {{ default_duration }} 秒，打斗 / 大场面 / 情绪铺陈等画面可取更长档至 {{ max_duration }} 秒，不要默认选最短档{% else %}从支持的秒数档位（{{ durations }}）中按画面内容复杂度匹配合适时长（最长 {{ max_duration }} 秒），不强制默认值{% endif %}。
  - 口播下界：先估算该场 utterances（台词 + 画外音）念完约需的秒数（口播语速约 {{ speech_rate }} {{ speech_unit }}/秒，按受众理解需要留出停顿，不靠加速念完），再计入不能与口播同时完成的动作、换人接话和结果反应时间，在上述档位里取**不低于**所需时间的最接近档位；utterances 为空仍需估算动作时间。若超过最长 {{ max_duration }} 秒，沿自然语句或动作边界拆成连续分镜，直到每镜可完成，禁止仅把时长封顶。逐字保留的口播拆分后须按原顺序拼回原文，不删减、不重复；同一场次内拆镜不表示场景切换。
{% if episode_target_duration %}
  - 单集目标：{{ partial("shared/episode_target_duration_rule") }}。
{% endif %}
- **segment_break**：{{ variant("text/drama_script_plan/break_rule", source_kind) }}
- **characters_in_scene** / **scenes** / **props**：从下列候选中列出此分镜实际出现的资产。
  - 候选 characters：[{{ character_names | join(", ") or "（暂无）" }}]
  - 候选 scenes：[{{ scene_names | join(", ") or "（暂无）" }}]
  - 候选 props：[{{ prop_names | join(", ") or "（暂无）" }}]
  - 候选里没有的资产写原文称呼，并列进 `new_assets`（见下文）；泛指群演（如「老人甲」「村民若干」）不进 characters_in_scene。
- **scene_description**：{{ variant("text/drama_script_plan/scene_rule", source_kind) }}
  - 按“开始状态 → 主要动作 → 结束状态”写清可见的变化与承接；这是完整镜头的内容依据，后续 image_prompt 只取其中的起始状态。实际出镜的已登记资产须同步列入本镜引用字段，不得漏掉关键道具。

## 逐字内容（内容真相源，定稿后原样保留、不再改写）

- **source_text**：逐字摘录本分镜对应的原文片段，尽量与原文一致、宁缺毋造（无把握可留空）。
- **utterances**：{{ variant("text/drama_script_plan/utterances_rule", source_kind) }}

每个分镜是一个可在指定时长内完成的连续镜头，通常只承担一个主要事件；不要把准备、尝试、失败、反应等多个叙事阶段或快速剪辑塞进同一镜。独立生成不等于故事独立，相邻镜头必须能按顺序理解。

输出前按顺序检查一遍：忽略 source_text 和未说出的设定，只看 scene_description 与 utterances，确认关键因果可见、空间与物品状态连贯、每次动作只发生一次、台词与动作放得进时长。修正拆镜引入的遗漏、重复和矛盾；不要为凑单集目标时长省略必要衔接或压缩实际所需时间。

{{ partial("shared/new_assets_rule") }}
{% if instructions %}

{{ partial("shared/additional_instructions") }}
{% endif %}
