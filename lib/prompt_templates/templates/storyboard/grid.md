---
id: storyboard/grid
category: storyboard
title: 宫格联合图
description: >-
  把一组分镜的静态首帧按顺序画进一张宫格联合图，每格与一个分镜一一对应，生成后按画格切回各分镜。
  画格等大、无边框、无间隙、不合并不遗漏已由布局要求正面写明，Avoid 行只追加布局要求没覆盖到的
  反面形态（边框、间隙或留白、合并 / 缺失 / 错位、连续全景），不再重复质量词、拼贴感、
  纯色背景条与画格大小比例。
  末块分镜不足一档时由空占位格补齐，占位格画成纯灰，切格后丢弃。
applies_to: {}
slots:
  reference_images: 参考图类型声明，按随请求发出的参考图序位编号为「图N」；无参考图为空
  rows: 宫格行数
  cols: 宫格列数
  cell_count: 画格总数
  grid_aspect_ratio: 整张联合图的比例
  panel_aspect_ratio: 单个画格的比例，由整图比例与行列数算出
  cells: 静态首帧列表（index、row、col、scene_id、description、roster）
  placeholders: 空占位格列表（index、row、col）
  character_identities: 角色身份段（预渲染，无角色时为空）
  style: 项目画风
  style_description: 项目风格描述
protected: false
---
{% if reference_images %}
Reference_Images: {{ reference_images }}

{% endif %}
你是一位专业的分镜画师。请严格按照 {{ rows }}×{{ cols }} 宫格布局生成一张包含恰好 {{ cell_count }} 个等大画格的联合图。

【布局要求】
- 恰好 {{ rows }} 行 {{ cols }} 列，共 {{ cell_count }} 个画格，阅读顺序：从左到右，从上到下
- 整体图片比例：{{ grid_aspect_ratio }}
- 每个画格比例：{{ panel_aspect_ratio }}，所有画格大小完全相同
- 画格之间无边框、无间隙、无留白，紧密排列
- 不得合并画格、不得遗漏画格、不得错位排列
- 所有画格保持一致的角色外观、光线和色彩风格

{% if character_identities %}
{{ character_identities }}

【外观优先级】
- 已绑定的角色资产图是人物外观依据：脸部结构、年龄感、发型、头身比例、默认服装与配饰以各自参考图为准，不把不同角色的造型分配给对方。
- 本格正文只决定动作准备、位置、视线、表情与道具互动；若正文外观措辞与角色参考图冲突，采用参考图外观。换装以本格明确绑定的衍生角色资产为准，不自行设计新衣服。
- 全局风格用于环境、光照和整体呈现，不得覆盖角色参考图的造型，不得统一重塑面孔、放大眼睛或把成年角色幼态化。角色设计图中的多个视角是同一身份，不是多个人。
{% endif %}
【逐格首帧】
- 每格只画对应分镜主要动作开始前的一个静态瞬间，严格按下方编号与位置一一对应。
- 不把动作过程拆成额外画格，不重演上一格的动作，不移动后续画格来容纳额外画面。
- 每格只使用本格角色清单与画面内容，不把相邻格人物带入本格；切换人物或景别不代表两镜人物必须同框。
- 同一时空的角色外观、空间关系与光照保持连贯，但不强制把前一镜结束与后一镜开始合并为同一个画面。
- 全息、透明、发光等效果只改变呈现方式，不改变被投影角色的脸部结构、年龄感或身体比例。
- 成图前逐格核对镜头归属、主体数量和身份：无漏格、增格、错位，无错穿服装、面孔混合或成年角色幼态化。

【各格内容】
{{ partial("storyboard/grid/lists/cells") }}

{{ partial("shared/style") }}

{{ partial("storyboard/grid/avoid") }}
