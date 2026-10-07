{% for cell in cells %}
格{{ cell.index }}（row{{ cell.row }} col{{ cell.col }}）— {{ cell.scene_id }}首帧：
{% if cell.roster %}{{ cell.roster }}
{% endif %}  {{ cell.description }}
{% endfor %}
{% for cell in placeholders %}
格{{ cell.index }}（row{{ cell.row }} col{{ cell.col }}）— 空占位：纯灰色背景，无任何内容
{% endfor %}
