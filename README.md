# Meng Magazine PDF · 门哥的杂志式 PDF

门哥认可的定稿 v3：暖米色纸面、大黑体与轻宋体、朱红章节页、连续跨页照片、窄栏正文、图形化预算及深色封底。

这是完整技能包，包含说明、排版脚本、完整字体、配置和六页参考样张。适用于旅行、书店方案、提案、纪念册与长文。

## 让其他 AI 使用

把仓库链接连同下面这段话发给有文件操作与 Python 执行能力的 AI：

> 请读取 https://github.com/sadjdg123/meng-magazine-pdf 的 SKILL.md，以及它引用的 references 文件；下载完整仓库并查看 assets/editorial/approved-preview.jpg 与 approved-reference.pdf。按这套技能制作本次 PDF，使用现有排版脚本和字体，遵守素材来源与全页渲染检查要求。参考文件中的旅行内容只是示例，本次内容以我提供的材料为准。

只有网页阅读能力的 AI 可以理解风格；要实际生成 PDF，还需要下载仓库、安装依赖并运行 Python。只读 SKILL.md 不足以完整复现。

## 本地运行

需要 Python 3，建议使用独立虚拟环境。

```sh
git clone https://github.com/sadjdg123/meng-magazine-pdf.git
cd meng-magazine-pdf
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
mkdir -p output
python scripts/compose.py assets/editorial/approved.json output/approved.pdf
```

输出 PDF 和同名 `.qa.json`。先检查 QA，再渲染并检查全部页面。使用 PDF 能力工具或 Poppler `pdftoppm` 可做页面渲染；Poppler 是系统工具，不在 Python 依赖清单中。

新任务复制输入 JSON 到任务目录，修改内容与图片路径，按 [输入格式](references/input-schema.md) 准备素材记录；不要改写样张来保存自己的新内容。

## 主要文件

- [SKILL.md](SKILL.md)：AI 的工作入口与制作流程。
- [设计规范](references/style-guide.md)、[输入格式](references/input-schema.md)、[素材流程](references/media-workflow.md)。
- [六页预览](assets/editorial/approved-preview.jpg)、[认可样张 PDF](assets/editorial/approved-reference.pdf)。
- `scripts/`：排版、素材检查与回归脚本。
- `assets/style.json`、`assets/layouts.json`：统一样式和版式配置。
- `assets/fonts/`：完整字体及 OFL 许可。

## 素材和范围

默认原创概念封面配真实内页照片；用户指定素材时遵从本次要求。照片的来源、作者、许可与裁切须保留。示例照片的来源和许可见 `assets/editorial/approved.json` 与 `assets/examples/travel.json`；字体按各自 OFL 使用。第三方素材的许可不因进入本仓库而改变。

当前输出为 RGB 屏幕阅读稿，不声称 PDF/X、CMYK 或 PDF/UA 认证。
