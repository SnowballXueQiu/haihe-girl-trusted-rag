"""旧版系统说明书及配套材料生成器。

正式参赛论文以 ``paper/main.tex`` 和 ``scripts/build_paper.sh`` 的 LaTeX
编译结果为准。本脚本保留用于生成归档版说明书、AI 声明和运行说明，
不得用旧版说明书替代正式论文。
"""

from __future__ import annotations

import re
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    Image,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "pdf"
NAVY = colors.HexColor("#102743")
INK = colors.HexColor("#253448")
MUTED = colors.HexColor("#66768A")
PALE = colors.HexColor("#F2F5F7")
PINK = colors.HexColor("#E98A9D")
ROSE = colors.HexColor("#FFF0F2")
RED = colors.HexColor("#B94452")
CYAN = colors.HexColor("#7EDCE1")
GOLD = colors.HexColor("#D8B56B")
GREEN = colors.HexColor("#2C8A72")


def register_fonts() -> None:
    # ReportLab cannot embed the CFF outlines used by the local Noto CJK OTF.
    # Arial Unicode is a TrueType font with complete Simplified Chinese glyphs.
    regular = Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf")
    bold = regular
    pdfmetrics.registerFont(TTFont("CJK", str(regular)))
    pdfmetrics.registerFont(TTFont("CJKBold", str(bold if bold.exists() else regular)))


register_fonts()
STYLES = getSampleStyleSheet()
BODY = ParagraphStyle(
    "body", parent=STYLES["BodyText"], fontName="CJK", fontSize=9.4,
    leading=16, textColor=INK, spaceAfter=4,
)
SMALL = ParagraphStyle(
    "small", parent=BODY, fontSize=7.7, leading=12, textColor=MUTED,
)
H1 = ParagraphStyle(
    "h1", parent=STYLES["Heading1"], fontName="CJKBold", fontSize=24,
    leading=32, textColor=NAVY, spaceAfter=12,
)
H2 = ParagraphStyle(
    "h2", parent=STYLES["Heading2"], fontName="CJKBold", fontSize=15,
    leading=21, textColor=NAVY, spaceBefore=7, spaceAfter=8,
)
H3 = ParagraphStyle(
    "h3", parent=STYLES["Heading3"], fontName="CJKBold", fontSize=10.5,
    leading=15, textColor=RED, spaceBefore=5, spaceAfter=4,
)
CAPTION = ParagraphStyle(
    "caption", parent=SMALL, alignment=TA_CENTER, fontSize=7.2, spaceBefore=3,
)
WHITE_TITLE = ParagraphStyle(
    "white-title", parent=H1, fontSize=28, leading=37, textColor=colors.white,
)
WHITE_SUB = ParagraphStyle(
    "white-sub", parent=BODY, fontSize=11.5, leading=19, textColor=colors.HexColor("#D8E4EF"),
)
SUPPORT_BODY = ParagraphStyle(
    "support-body", parent=BODY, fontSize=9.1, leading=14.2, spaceAfter=2.4,
)
SUPPORT_H2 = ParagraphStyle(
    "support-h2", parent=H2, fontSize=14.2, leading=19, spaceBefore=5, spaceAfter=6,
)
SUPPORT_H3 = ParagraphStyle(
    "support-h3", parent=H3, fontSize=10.2, leading=14, spaceBefore=4, spaceAfter=3,
)
SUPPORT_CODE = ParagraphStyle(
    "support-code", parent=SMALL, fontSize=7.8, leading=11.2, textColor=NAVY,
)


def p(text: str, style: ParagraphStyle = BODY) -> Paragraph:
    return Paragraph(text, style)


def bullets(items: list[str]) -> list[Flowable]:
    return [Paragraph(f"•&nbsp;&nbsp;{escape(item)}", BODY) for item in items]


def section(number: str, title: str) -> list[Flowable]:
    return [Spacer(1, 3 * mm), p(f"{number}&nbsp;&nbsp;{escape(title)}", H1)]


def status_box(label: str, text: str, color: colors.Color = GREEN) -> Table:
    table = Table(
        [[p(label, ParagraphStyle("boxlabel", parent=SMALL, fontName="CJKBold", textColor=color)),
          p(text, ParagraphStyle("boxtext", parent=BODY, fontSize=8.5, leading=13))]],
        colWidths=[28 * mm, 137 * mm],
        hAlign="LEFT",
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PALE),
        ("BOX", (0, 0), (-1, -1), 0.7, color),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return table


class Architecture(Flowable):
    def __init__(self, width: float = 165 * mm, height: float = 69 * mm):
        super().__init__()
        self.width = width
        self.height = height

    def draw(self) -> None:
        c = self.canv
        c.setLineWidth(0.8)
        boxes = [
            (0, 43, 29, 18, "React 主播台", PINK),
            (38, 43, 32, 18, "FastAPI\nSSE", CYAN),
            (79, 43, 38, 18, "可信编排器", GOLD),
            (127, 50, 38, 13, "Qwen 生成", PALE),
            (127, 31, 38, 13, "Qwen TTS", PALE),
            (79, 4, 38, 18, "混合检索", CYAN),
            (31, 4, 38, 18, "SQLite FTS5\n+ 向量", PALE),
            (0, 4, 22, 18, "12 来源\n审核入库", ROSE),
        ]
        for x, y, w, h, label, fill in boxes:
            x *= mm; y *= mm; w *= mm; h *= mm
            c.setFillColor(fill)
            c.setStrokeColor(NAVY)
            c.roundRect(x, y, w, h, 2.3 * mm, fill=1, stroke=1)
            c.setFillColor(NAVY)
            c.setFont("CJKBold", 7.5)
            lines = label.split("\n")
            for i, line in enumerate(lines):
                c.drawCentredString(x + w / 2, y + h / 2 + (len(lines) / 2 - i - .75) * 9, line)

        def arrow(x1: float, y1: float, x2: float, y2: float) -> None:
            c.setStrokeColor(MUTED); c.setFillColor(MUTED)
            c.line(x1 * mm, y1 * mm, x2 * mm, y2 * mm)
            c.circle(x2 * mm, y2 * mm, 1.2, fill=1, stroke=0)

        arrow(29, 52, 38, 52); arrow(70, 52, 79, 52); arrow(117, 55, 127, 56)
        arrow(117, 48, 127, 38); arrow(98, 43, 98, 22); arrow(79, 13, 69, 13)
        arrow(31, 13, 22, 13)
        c.setFont("CJK", 6.2); c.setFillColor(MUTED)
        c.drawString(3 * mm, 65 * mm, "文字问答 · 证据卡 · VRM · 音频口型")


class GateFlow(Flowable):
    def __init__(self, width: float = 165 * mm, height: float = 64 * mm):
        super().__init__(); self.width = width; self.height = height

    def draw(self) -> None:
        c = self.canv
        steps = [
            ("问题输入", "主题/攻击检查"), ("召回", "FTS5 + 向量"),
            ("证据门控", "相关度/来源"), ("生成", "仅依据片段"),
            ("引用校验", "ID + 语义一致"), ("播报", "一次性令牌"),
        ]
        gap = 4.5 * mm; w = (165 * mm - gap * 5) / 6; y = 28 * mm
        for i, (title, sub) in enumerate(steps):
            x = i * (w + gap)
            c.setFillColor(ROSE if i in (2, 4) else PALE)
            c.setStrokeColor(RED if i in (2, 4) else NAVY)
            c.roundRect(x, y, w, 23 * mm, 2 * mm, fill=1, stroke=1)
            c.setFont("CJKBold", 7.8); c.setFillColor(NAVY)
            c.drawCentredString(x + w / 2, y + 14 * mm, title)
            c.setFont("CJK", 5.9); c.setFillColor(MUTED)
            c.drawCentredString(x + w / 2, y + 7 * mm, sub)
            if i < 5:
                c.setStrokeColor(MUTED); c.line(x + w, y + 11.5 * mm, x + w + gap, y + 11.5 * mm)
        c.setFont("CJKBold", 8); c.setFillColor(RED)
        c.drawString(0, 17 * mm, "任一关失败  →  固定拒答“当前知识库没有足够依据”  →  不签发语音令牌")
        c.setFont("CJK", 7); c.setFillColor(MUTED)
        c.drawString(0, 8 * mm, "有效回答的每个事实段都必须绑定当次召回结果中存在的 citation_id。")


def image_card(path: Path, width: float, caption: str) -> KeepTogether:
    img = Image(str(path))
    img._restrictSize(width, 93 * mm)
    return KeepTogether([img, p(caption, CAPTION)])


def table(rows: list[list[str]], widths: list[float], header: bool = True) -> Table:
    data = [[p(escape(cell), ParagraphStyle("cell", parent=SMALL, textColor=INK)) for cell in row] for row in rows]
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    commands = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CED7DE")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1), [colors.white, PALE]),
    ]
    if header:
        commands += [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white)]
        for item in data[0]:
            item.style.textColor = colors.white
            item.style.fontName = "CJKBold"
    t.setStyle(TableStyle(commands))
    return t


class ReportDoc(BaseDocTemplate):
    def __init__(self, filename: str, title: str):
        super().__init__(filename, pagesize=A4, rightMargin=20 * mm, leftMargin=20 * mm,
                         topMargin=18 * mm, bottomMargin=18 * mm, title=title, author="海河少女项目组")
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="main")
        self.addPageTemplates(PageTemplate(id="page", frames=frame, onPage=self.draw_page))

    def draw_page(self, canvas, doc) -> None:
        page = canvas.getPageNumber()
        if page == 1:
            return
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#DCE3E8")); canvas.line(20 * mm, 13 * mm, 190 * mm, 13 * mm)
        canvas.setFont("CJK", 6.7); canvas.setFillColor(MUTED)
        canvas.drawString(20 * mm, 8.2 * mm, "海河少女 · 可信 RAG 虚拟主播系统")
        canvas.drawRightString(190 * mm, 8.2 * mm, f"{page:02d}")
        canvas.restoreState()


def build_design_pdf() -> Path:
    output = OUT / "海河少女可信RAG虚拟主播系统旧版说明书.pdf"
    doc = ReportDoc(str(output), "海河少女可信RAG虚拟主播系统旧版说明书")
    story: list[Flowable] = []

    avatar = ROOT / "frontend/public/avatar-placeholder.jpg"
    cover_image = Image(str(avatar), width=66 * mm, height=66 * mm)
    cover = Table([
        [p("方向 A · AI 智能体创作系统设计", ParagraphStyle("kicker", parent=WHITE_SUB, fontName="CJKBold", textColor=CYAN)), ""],
        [p("海河少女<br/><font size='17'>基于可信 RAG 的天津文化<br/>AI 虚拟主播系统</font>", WHITE_TITLE), cover_image],
        [p("旧版系统设计说明书（归档） / 正式论文以 LaTeX 版为准", WHITE_SUB), ""],
    ], colWidths=[103 * mm, 62 * mm], rowHeights=[20 * mm, 91 * mm, 19 * mm])
    cover.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("SPAN", (0, 2), (1, 2)), ("LEFTPADDING", (0, 0), (-1, -1), 11 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7 * mm), ("TOPPADDING", (0, 0), (-1, -1), 5 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5 * mm),
    ]))
    story += [Spacer(1, 13 * mm), cover, Spacer(1, 11 * mm),
              status_box("设计原则", "证据先于表达。系统仅在人工审核的限定知识库中检索；没有足够证据时明确拒答，未通过引用校验的内容不进入 TTS 播报。", PINK),
              p("学校：____________________&nbsp;&nbsp;&nbsp;&nbsp;作者：____________________&nbsp;&nbsp;&nbsp;&nbsp;指导教师：____________________", SMALL),
              PageBreak()]

    story += section("01", "作品概述")
    story += [p("“海河少女”将天津地域文化视觉 IP、可检查的知识回答和实时三维主播表现合为一个本地 Demo。用户输入中文问题后，系统先检索人工审核的文档，再组织带出处的回答，并通过语音驱动角色口型。"),
              Architecture(), p("图 1  系统组件和数据边界", CAPTION),
              p("已锁定范围", H2)]
    story += bullets(["中文单语；文字提问+语音播报，不做麦克风 ASR。",
                      "知识主题只覆盖角色设定、泥人张、风筝魏、海河文化与天津海棠。",
                      "Mac 负责正式演示；交付跨平台源码和 Windows/macOS 运行说明。",
                      "不建设公网地址；云服务失败时展示错误，不使用预录回答。"])
    story += [p("创新点", H2), table([
        ["维度", "设计"],
        ["文化表达", "角色色彩、服装细节与天津文化符号关联，由三维形象完成亲和的公共叙事。"],
        ["可信交互", "不把“有引用”等同于“绝对正确”；用证据门控、引用白名单和二次核验降低无依据回答。"],
        ["视听联动", "仅校验通过的文本获取一次性语音令牌；音频振幅驱动 VRM 口型。"],
    ], [28 * mm, 137 * mm])]
    story.append(PageBreak())

    story += section("02", "角色与视觉设计")
    process_a = ROOT / "海河少女/人物设计过程/3cdfb743e2d76f972399badb1bd1d1c1.png"
    process_b = ROOT / "海河少女/人物设计过程/8fc0881b93edd0a068ebc5579a076749.png"
    story += [p("角色定位为“了解天津手工艺与海河城市文化的年轻讲述者”。深蓝、海河青和海棠粉构成主色，胸前纹样及服饰层次用于传递地域记忆，不将二次创作设定宣称为历史事实。"),
              image_card(process_a, 165 * mm, "图 2  角色造型制作过程截图"),
              Spacer(1, 3 * mm), image_card(process_b, 165 * mm, "图 3  角色细节调整过程截图"), PageBreak()]
    story += section("03", "可信 RAG 工作流")
    story += [GateFlow(), p("图 4  从输入到可播报回答的六道门控", CAPTION),
              p("拒答不是最后补丁，而是与正常回答同级的产品状态。对超出范围、实时信息、提示词攻击或证据较弱的输入，系统返回统一拒答，保留可解释的原因码。"),
              p("关键规则", H2)]
    story += bullets(["运行时不进行网页搜索，不把当前价格、营业时间等实时信息交给模型猜测。",
                      "一个事实段的 citation_id 必须存在于当次检索结果；回答数字和日期必须原样出现在所引证据中。",
                      "角色创作设定标记为 creative，学术和官方来源标记为 factual，生成提示中保留类型。",
                      "语音接口只接受服务端签发的短时一次性 token，不接受前端任意文本。"])
    story += [p("拒答语：“当前知识库没有足够依据”。", ParagraphStyle("quote", parent=BODY, fontName="CJKBold", fontSize=12, leading=19, textColor=RED, backColor=ROSE, borderPadding=9)), PageBreak()]

    story += section("04", "知识库和检索设计")
    story += [p("入库脚本读取 PDF、DOCX 和已审核 Markdown，在标题/页码边界内按约 400 字切块。数据库保留来源 ID、标题、发布者、页码、原文片段、URL、内容哈希和来源类型。"),
              table([
                  ["来源类别", "数量", "作用", "边界"],
                  ["原创角色文档", "2", "服装、个性、世界观", "标记为艺术创作"],
                  ["学术文献", "6", "设计方法、非遗研究、虚拟人研究", "按页码引用"],
                  ["官方资料摘编", "4", "泥人张、风筝魏、海河、海棠", "保留官方 URL 和摘编日期"],
              ], [36 * mm, 15 * mm, 56 * mm, 58 * mm]),
              p("混合检索", H2),
              p("词法通道使用 SQLite FTS5，语义通道使用归一化向量余弦相似度。两路候选经 Reciprocal Rank Fusion 融合，再根据关键词覆盖率和来源多样性门控。为避免长论文淹没其他证据，单来源最多返回 2 个知识块。"),
              p("向量配置：本地开发 qwen3-embedding:4b；正式配置 qwen3.7-text-embedding，1024 维。不同模型的索引不混用，切换配置后必须重建。", SMALL), PageBreak()]

    story += section("05", "接口与数据结构")
    story += [table([
        ["接口", "输入", "输出", "安全约束"],
        ["GET /api/health", "无", "索引、生成、TTS、VRM 状态", "不暴露密钥"],
        ["POST /api/query", "question, session_id", "SSE: status / evidence / token / final / error", "参数限长，先门控后生成"],
        ["POST /api/speech", "speech_token", "流式 WAV 音频", "token 一次性且过期失效"],
        ["GET /api/sources/{id}", "source_id", "本地文件或官方 URL 描述", "仅访问登记来源"],
    ], [36 * mm, 36 * mm, 55 * mm, 38 * mm]),
    p("Citation 字段", H2),
    table([
        ["字段", "含义"], ["source_id", "稳定的来源标识"], ["title", "来源标题"],
        ["publisher", "作者、期刊或官方发布单位"], ["page", "PDF/DOCX 页码或章节"],
        ["excerpt", "支撑当前回答的原文片段"], ["url", "官方来源链接；本地文档可为空"],
    ], [38 * mm, 127 * mm]),
    p("生成结果先以结构化 JSON 返回段落和 citation_id。后端不相信模型自报的引用，而是用当次候选集合重建 Citation，并在二次核验后签发语音 token。"), PageBreak()]

    story += section("06", "前端与虚拟主播")
    story += [p("页面采用“宣纸、玉石、青砖灰”视觉语言，以大留白承载三维文化向导；津门蓝用于主要操作，朱砂红只作点睛和拒答提示，回答与引用使用轻量数字玻璃层。"),
              table([
                  ["模块", "交互与状态"],
                  ["主播舞台", "VRM 半身展示；自然眨眼、呼吸待机、指针视线跟随，音频振幅驱动 Aa 表情。"],
                  ["问题区", "6 个预设问题和自由文本输入；连接 SSE 后展示检索、核验和生成阶段。"],
                  ["回答区", "流式字幕；成功、拒答和服务错误三种明确状态。"],
                  ["证据区", "展开引用卡后可查看标题、发布者、页码、片段和官方 URL。"],
                  ["可信状态", "顶部显示索引、生成、语音和 VRM 就绪情况；异常不伪装成正常。"],
              ], [34 * mm, 131 * mm]),
              status_box("当前模型状态", "haihe-girl.vrm 已原样接入并通过 VRM 1.0 结构与 1920×1080 浏览器加载检查；百炼新加坡非实时 HTTP TTS 与语音接口已完成实测。正式录屏前仍需复核口型、停止与重播，并由权利人确认模型书面授权和署名。", RED), PageBreak()]

    story += section("07", "模型、语音与运行配置")
    story += [table([
        ["用途", "本地开发", "正式演示"],
        ["回答生成", "Ollama qwen3.5:27b", "qwen3.7-flash-2026-07-15"],
        ["文本向量", "Ollama qwen3-embedding:4b", "qwen3.7-text-embedding / 1024 维"],
        ["语音合成", "不使用预录备份", "qwen3-tts-flash-2025-11-27 / Serena / Chinese"],
        ["密钥", "无", "仅本机 .env，不进入源码和参赛包"],
    ], [35 * mm, 62 * mm, 68 * mm]),
    p("正式演示使用固定快照，避免在验收期间因默认别名更新导致行为漂移。百炼配置使用已验证的新加坡业务空间，敏感连接参数仅存于本机 .env，不进入论文、截图或参赛包。生产索引已使用同一 1024 维向量配置重建。"),
    p("故障可见性", H2)]
    story += bullets(["索引不存在：页面状态显示未就绪，接口不返回伪造证据。",
                      "Ollama 或百炼不可用：返回明确错误信息，保留当次引用列表供排查。",
                      "TTS 失败：文字和引用仍可查看，不播放本地录音假冒云端合成语音。",
                      "VRM 缺失：使用静态占位图，不影响知识门控的开发和测试。"])
    story.append(PageBreak())

    story += section("08", "测试与验收")
    story += [p("评测集固定为 60 题，用于同时验证“答对”和“该拒时拒答”。本地配置和百炼正式配置分别留存评测记录，避免把本地索引结果冒充生产结果。"),
              table([
                  ["题型", "数量", "预期", "关键指标"],
                  ["库内题", "40", "回答并给出有效证据", "Recall@6 ≥ 90%"],
                  ["越界题", "10", "固定拒答", "10/10 拒答"],
                  ["歧义题", "5", "证据不足时拒答", "0 无依据事实"],
                  ["提示词攻击", "5", "检索前拦截", "5/5 拒答"],
              ], [38 * mm, 18 * mm, 55 * mm, 54 * mm]),
              status_box("本地与生产已验证", "2026-09-13：28 项单测通过，包含百炼向量接口临时 403 重试覆盖；本地固定 60 题为库内 40/40、拒答 20/20。百炼生产向量 60 题同样为 Top-6 命中 40/40、拒答 20/20；正式 API 20 轮为 20/20，其中 2 轮真实语音接口返回 HTTP 200。", GREEN),
              p("验收记录与待办", H2)]
    story += bullets(["本地与百炼正式 API 均完成 20 轮复测；Chrome 已检查正常回答、有效引用、拒答和新 VRM 加载。",
                      "所有事实回答都存在可打开的来源，页码或章节与引用片段匹配。",
                      "单元测试、前端生产构建、索引构建、检索评测和浏览器交互验收均有可复现命令。",
                      "待办：浏览器音频口型、停止与重播复核，以及 1920×1080 H.264、3–5 分钟最终视频。"])
    story += [status_box("“不瞎编”定义", "证据门控+测试集内零无依据回答；不声称大语言模型在理论上绝对不会产生幻觉。", RED), PageBreak()]

    story += section("09", "开发排期和风险管理")
    story += [table([
        ["日期", "工作", "出口条件"],
        ["9月13–14日", "锁定学校截止；VRM 技术验收与书面授权；验证百炼新加坡业务空间", "三类模型最小调用、生产索引与正式 API 通过"],
        ["9月15–16日", "归档百炼生产 60 题和 20 轮 API；复核 TTS 与口型", "40/40 命中、20/20 拒答；停止和重播可用"],
        ["9月17日", "完成前端视觉和预设问题收口", "1920×1080 布局稳定"],
        ["9月18–19日", "复核已归档的 60 题与 20 轮 API；完成故障演练", "报告与当前配置一致；失败不伪造回答"],
        ["9月20日", "报名表、作品授权书、版权表和模型授权证明", "签章、许可和隐私字段复核完成"],
        ["9月21日", "录制 3–5 分钟视频；编译 LaTeX 论文", "视频编码合规；论文逐页渲染通过"],
        ["9月22日", "版本冻结、干净环境复现、打包与异地验包", "完整性、500 MB 和密钥检查全绿"],
        ["9月23日", "学校提交、链接验证和回执留档", "不安排开发；确认提交成功"],
    ], [31 * mm, 83 * mm, 51 * mm]), PageBreak()]

    story += section("10", "交付清单与当前状态")
    story += [table([
        ["交付物", "当前状态", "完成条件"],
        ["可运行 Demo 与源码", "主体、VRM 与百炼链路已验证", "确认模型授权；完成浏览器音频交互复核"],
        ["知识库与 60 题评测", "本地和生产均已评测", "归档与当前索引和模型配置一致的报告"],
        ["系统设计 PDF", "本文档", "填写学校、作者和指导教师"],
        ["AI 声明/人机协作记录", "已建立", "团队确认实际使用工具和版本"],
        ["3–5 分钟 H.264 MP4", "待正式录制", "确认 VRM 授权；完成浏览器录屏彩排"],
        ["报名表、授权书", "待学校模板", "确定不超过 2 名学生、1 名指导教师"],
        ["学校名+作品名参赛包", "可生成草案", "补齐上述材料，检查小于 500MB 且无密钥"],
    ], [45 * mm, 35 * mm, 85 * mm]),
    Spacer(1, 7 * mm), status_box("提交前最后四项", "1. 取得 VRM 书面授权并确认署名和隐私；2. 复核浏览器音频口型、停止与重播；3. 录制并验收正式视频；4. 向学校取得并填写报名表与授权书。", GOLD),
    Spacer(1, 20 * mm), p("证据是主播开口前的最后一道门。", ParagraphStyle("end", parent=H1, alignment=TA_CENTER, textColor=RED)),
    p("— 海河少女可信 RAG 虚拟主播系统", ParagraphStyle("endsub", parent=SMALL, alignment=TA_CENTER))]

    doc.build(story)
    return output


def _markdown_inline(text: str) -> str:
    rendered = escape(text)
    rendered = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", rendered)
    rendered = re.sub(
        r"`([^`]+)`",
        r'<font color="#315C72">\1</font>',
        rendered,
    )
    return rendered


def _code_table(lines: list[str]) -> Table:
    content = "<br/>".join(escape(line) if line else "&nbsp;" for line in lines)
    block = Table([[p(content, SUPPORT_CODE)]], colWidths=[165 * mm], hAlign="LEFT")
    block.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PALE),
        ("BOX", (0, 0), (-1, -1), 0.45, colors.HexColor("#CED7DE")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return block


def markdown_lines_to_story(path: Path, title: str, intro: str) -> list[Flowable]:
    story: list[Flowable] = [
        Spacer(1, 6 * mm), p(title, H1), p(intro, SUPPORT_BODY), Spacer(1, 2 * mm)
    ]
    in_code = False
    code_lines: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("```"):
            if in_code:
                story.extend([_code_table(code_lines), Spacer(1, 1.5 * mm)])
                code_lines = []
            in_code = not in_code
            continue
        if in_code:
            code_lines.append(raw.rstrip())
            continue
        if not line:
            story.append(Spacer(1, 1 * mm))
        elif line.startswith("# "):
            continue
        elif line.startswith("## "):
            story.append(p(_markdown_inline(line[3:]), SUPPORT_H2))
        elif line.startswith("### "):
            story.append(p(_markdown_inline(line[4:]), SUPPORT_H3))
        elif line.startswith("- "):
            story.append(p("•&nbsp;&nbsp;" + _markdown_inline(line[2:]), SUPPORT_BODY))
        elif re.match(r"\d+\.\s", line):
            story.append(p(_markdown_inline(line), SUPPORT_BODY))
        else:
            story.append(p(_markdown_inline(line), SUPPORT_BODY))
    if code_lines:
        story.append(_code_table(code_lines))
    return story


def build_supporting_pdf(source: str, output_name: str, title: str, intro: str) -> Path:
    output = OUT / output_name
    doc = ReportDoc(str(output), title)
    doc.build(markdown_lines_to_story(ROOT / source, title, intro))
    return output


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    outputs = [
        build_design_pdf(),
        build_supporting_pdf("docs/AI工具使用声明.md", "AI工具使用声明.pdf", "AI 工具使用声明", "本文档记录作品中 AI 的实际用途、人机协作边界、数据隐私和技术局限。"),
        build_supporting_pdf("docs/人机协作过程说明.md", "人机协作过程说明.pdf", "人机协作过程说明", "记录参赛团队和 AI 工具在需求、开发、资料审核和验收中的分工。"),
        build_supporting_pdf("docs/运行与操作说明.md", "运行与操作说明.pdf", "运行与操作说明", "用于评审和复现演示的本地部署、配置、操作与故障处理指南。"),
    ]
    for output in outputs:
        print(output.relative_to(ROOT))


if __name__ == "__main__":
    main()
