# 输入格式与调用

运行 `python3 <skill-dir>/scripts/compose.py /absolute/content.json /absolute/output.pdf`。依赖Python 3、reportlab、fonttools、Pillow、PyMuPDF。资源相对于技能脚本定位；图片相对于内容JSON，可使用绝对路径。无需联网字体。新主题内容JSON放任务工作区，不放技能安装目录。

顶层：`title`、`modules`必需，`author`、`brand`、`edition`可选。按实际模块顺序生成PDF。每个模块的`name`用于PDF书签；书签可点击。spread占两页，contents按目录项数续页，其余设计模块一页；article与自动来源页按文字自然续页。`.qa.json`必须检查最终与分项结果。

复制 `assets/editorial/approved.json` 查看完整六页示例；复制后将图片改成正确绝对路径，别误用旅行图片。

顶层assets是图片记录列表，include_sources默认true。每个模块可指定唯一id；程序自动为未指定的模块生成id。in_contents=false隐藏该模块的目录条目；repeat_reason说明重复用图理由。网络图片与用户照片的具体记录见[素材流程](media-workflow.md)。

## 字段

| type | 必要字段 | 其他字段 |
|---|---|---|
| cover | title（1-2项字符串数组） | brand、edition、image、subtitle、footer、summary（纯字体封面时）、title_size |
| chapter | title | theme（red默认/dark）、kicker、number、intro、secondary_title、body、list_title、list_text、footer |
| spread | image、title、columns（恰好2项） | focus、kicker、intro、footer、right_title、steps（0-3项）、caption |
| budget | title、rows（1-5项） | kicker、unit、intro、axis_max、note_title、note、footer |
| half | image、title | kicker、focus、caption、intro、body、footer |
| pair | title、images（2项） | kicker、body、footer |
| contents | type | title、kicker、footer |
| article | blocks | columns（1默认/2）、running_title、footer |
| back | title | brand、edition、intro、byline、edition_note、credits、source_url、source_label、footer |

spread的columns每项为`{"title":"短小标题","text":"完整短段落"}`；steps每项为`{"title":"简短摘要","label":"说明"}`。两段窄栏各最多130 pt高，约6行；内容过长则完整放入后续article，不删掉关键条件。

budget的rows为`{"label":"方案名称","low":100,"high":200}`。输入必须满足0<=low<=high，axis_max至少覆盖最高值。未指定axis_max时按最大值推导整刻度；必须在unit/intro/note中说明单位与口径。数据超过五项放article表格。

所有标题数组限1-2行；明确编辑断行，不让最后两字单独成行。字段值均为纯文本，不传HTML。长字段触发容量错误，使用article保留全文，不重复在设计页里塞入长文。

pair的images每项为`{"image":"素材id","caption":"真实图注","focus":[0.5,0.5]}`。half和pair的正文为短文，超出容量转入article。所有嵌入图片必须对应assets记录，AI封面素材仅允许cover。

contents自动列出可导航的模块名称、全书页码与内部跳转链接；无需手填页码。模块name须清楚、简短。

## article

```json
{
  "type": "article",
  "name": "完整说明",
  "columns": 2,
  "running_title": "本次主题 / 正文",
  "footer": "为门哥准备",
  "blocks": [
    {"type": "h1", "text": "完整正文"},
    {"type": "intro", "text": "可选引言"},
    {"type": "h2", "text": "小标题"},
    {"type": "body", "text": "真实完整内容。长段落会续到下一栏或下一页。"},
    {"type": "small", "text": "资料标题", "link": "https://example.com/"}
  ]
}
```

article支持h1、h2、title、body、intro、small、label、kicker、quote、rule、space、day、image、table、toc、break。day需要label、title、text。image需要path，可加height、focus、caption、required（默认true）。table需要rows（首行表头）、widths（相对列宽）。toc需要items列表，其中label、anchor与有anchor的标题匹配。表格放columns=1的article，不能强行放半宽双栏。

```json
{"type":"table","rows":[["方案","设定"],["甲","100"]],"widths":[1,2]}
```

该底层也支持直接运行render.py处理旧blocks JSON，仅用于完整内容分页或开发回归。默认用户交付应通过compose.py组织有设计节奏的模块，不把旧19页报告重新当作模板。

## QA与边界

missing_text与out_of_page_text必须为空；设计模块的text_collisions必须为空；fonts全部embedded=true；article的分页稳定标志必须true。最终合并使用连续全书页码，不再擦除并重写页脚。整本目录和article内部目录均显示全书页码；链接在合并后重建并验证，整本另有模块书签。

images记录嵌入像素、有效ppi和原图哈希；assets记录实际素材。warnings逐项复核，尤其清晰度、主体裁切和重复用图。自动来源页默认开启，关闭的限制见素材流程。

回归命令：`python3 <skill-dir>/scripts/stress_test.py <临时目录>/stress` 和 `python3 <skill-dir>/scripts/regression_v3.py <临时目录>/modules`。技术fixture里的几何图仅用于测试裁切，不是真实照片或用户交付模板。

字体仅覆盖完整字体包含的字符。罕见字或其他文字出现缺字时先补字体；不要替换成近似字。封面图不能没有标题留白；图片来源与授权说明通过caption、credits或article来源区保留。
