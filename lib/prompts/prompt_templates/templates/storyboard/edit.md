---
id: storyboard/edit
category: storyboard
title: 分镜图编辑
description: 以当前分镜图为编辑底图，附加本镜角色资产图作为身份参考；只修改编辑指令指定的内容。
stage: storyboard_image
invoked_by:
  kind: generation_task
  name: image_edit
applies_to: {}
slots:
  instruction: 用户编辑指令
  references: 实际发送的底图与角色参考图编号声明
protected: false
---
Reference_Images: {{ references }}

图1是唯一编辑底图，保持其构图、画风、场景和未要求修改的内容。图2及之后的角色资产图只用于对应角色的身份与外观参考，不复制其版式、背景、姿势，不增加额外人物。除编辑指令明确要求的改变外，严格保持对应角色参考图中的脸型、眼形、眼距、鼻口比例、发际线、发型、头身比例、服装与配饰，不得混用不同角色的外观。

编辑指令：
{{ instruction }}
