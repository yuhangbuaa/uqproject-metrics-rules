"""在甲方模板副本中填写技术内容；未编辑包部件逐字节保留。"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import sys
from pathlib import Path
from zipfile import ZipFile
from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / ".work/midterm"
OUT = ROOT / "deliverables/中期检查材料_20261022"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}
def q(name): return f"{{{W}}}{name}"
def text(e): return "".join(x.text or "" for x in e.iter(q("t")))
def xml(data): return etree.fromstring(data)
def serialize(e): return etree.tostring(e, encoding="UTF-8", xml_declaration=True, standalone=True)


class Package:
    def __init__(self, path):
        self.path = Path(path)
        with ZipFile(path) as z: self.parts = {x.filename: z.read(x.filename) for x in z.infolist()}; self.infos = z.infolist()
        self.doc = xml(self.parts["word/document.xml"]); self.body = self.doc.find("w:body", NS)
        self.original = list(self.body)

    def p(self, index, value, heading=False, title=False):
        p = copy.deepcopy(self.original[index])
        if p.tag != q("p"): raise ValueError(index)
        ppr = p.find("w:pPr", NS)
        if ppr is None: ppr = etree.Element(q("pPr")); p.insert(0, ppr)
        for child in list(ppr):
            if child.tag in (q("sectPr"), q("pageBreakBefore")): ppr.remove(child)
        source_rpr = next(iter(p.findall("w:r/w:rPr", NS)), None)
        source_rpr = copy.deepcopy(source_rpr) if source_rpr is not None else copy.deepcopy(ppr.find("w:rPr", NS))
        for child in list(p):
            if child is not ppr: p.remove(child)
        for tag in ("keepNext", "keepLines"):
            old = ppr.find("w:" + tag, NS)
            if old is not None: ppr.remove(old)
        if heading: etree.SubElement(ppr, q("keepNext"))
        if title:
            style = ppr.find("w:pStyle", NS)
            if style is None: style = etree.SubElement(ppr, q("pStyle"))
            style.set(q("val"), "Title")
        r = etree.SubElement(p, q("r"))
        if source_rpr is not None: r.append(source_rpr)
        for i, line in enumerate(value.split("\n")):
            if i: etree.SubElement(r, q("br"))
            t = etree.SubElement(r, q("t")); t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve"); t.text = line
        return p

    def section(self, index):
        section = next(self.original[index].iter(q("sectPr")))
        section = copy.deepcopy(section)
        number = section.find("w:pgNumType", NS)
        if number is None: number = etree.SubElement(section, q("pgNumType"))
        number.set(q("start"), "1")
        return section

    def reset(self, nodes, section):
        for child in list(self.body): self.body.remove(child)
        for node in nodes: self.body.append(copy.deepcopy(node))
        self.body.append(copy.deepcopy(section))

    def write(self, path):
        replacements = {"word/document.xml": serialize(self.doc)}
        settings = xml(self.parts["word/settings.xml"])
        update = settings.find("w:updateFields", NS)
        if update is None: update = etree.SubElement(settings, q("updateFields"))
        update.set(q("val"), "true"); replacements["word/settings.xml"] = serialize(settings)
        styles = xml(self.parts["word/styles.xml"])
        if not any(s.get(q("styleId")) == "Title" for s in styles.findall("w:style", NS)):
            style = etree.SubElement(styles, q("style")); style.set(q("type"), "paragraph"); style.set(q("styleId"), "Title")
            name = etree.SubElement(style, q("name")); name.set(q("val"), "Title")
            based = etree.SubElement(style, q("basedOn")); based.set(q("val"), "Normal")
            replacements["word/styles.xml"] = serialize(styles)
        path.parent.mkdir(parents=True, exist_ok=True)
        with ZipFile(path, "w") as z:
            for info in self.infos: z.writestr(info, replacements.get(info.filename, self.parts[info.filename]))
        with ZipFile(path) as z:
            changed = [k for k, v in self.parts.items() if z.read(k) != v]
        if set(changed) - set(replacements): raise RuntimeError("保留部件发生变化")
        return {"file": str(path.relative_to(ROOT)), "source": str(self.path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "changedParts": changed}


def set_cell(cell, value):
    prototype = cell.find("w:p", NS)
    if prototype is None: prototype = etree.Element(q("p"))
    ppr = copy.deepcopy(prototype.find("w:pPr", NS))
    rpr = next(iter(prototype.findall("w:r/w:rPr", NS)), None)
    if rpr is None and ppr is not None: rpr = ppr.find("w:rPr", NS)
    rpr = copy.deepcopy(rpr)
    for e in list(cell):
        if e.tag != q("tcPr"): cell.remove(e)
    for line in value.split("\n"):
        p = etree.SubElement(cell, q("p"))
        if ppr is not None:
            props = copy.deepcopy(ppr)
            for tag in ("keepNext", "keepLines", "pageBreakBefore"):
                e = props.find("w:" + tag, NS)
                if e is not None: props.remove(e)
            p.append(props)
        r = etree.SubElement(p, q("r"))
        if rpr is not None: r.append(copy.deepcopy(rpr))
        etree.SubElement(r, q("t")).text = line or " "


def fill_table(prototype, values, blank=False):
    table = copy.deepcopy(prototype)
    if not blank:
        for height in table.findall(".//w:trHeight", NS): height.getparent().remove(height)
    for row in table.findall("w:tr", NS):
        cells = row.findall("w:tc", NS)
        if not cells: continue
        label = re.sub(r"\s+", "", text(cells[0]))
        if label in values:
            content = values[label]
            content = content if isinstance(content, list) else [content]
            for i, cell in enumerate(cells[1:]): set_cell(cell, content[min(i, len(content) - 1)])
        elif blank and label not in ("要素", "序号"):
            for cell in cells[1:]: set_cell(cell, "")
    return table


def pagebreak(package, prototype):
    p = package.p(prototype, "")
    etree.SubElement(p.find("w:pPr", NS), q("pageBreakBefore"))
    return p


def clean_cover(nodes):
    for e in nodes:
        for section in e.iter(q("sectPr")):
            number = section.find("w:pgNumType", NS)
            if number is None: number = etree.SubElement(section, q("pgNumType"))
            number.set(q("start"), "1")
        for t in e.iter(q("t")):
            value = t.text or ""
            if value.strip() in ("×密★×年", "×密", "x", "xx", "★", "×年", "（打印并盖章）", "（打印并签字）", "（打印并盖章）", "（打印并签字）"):
                t.text = "非密" if "密" in value else ""
            if value.strip() == "密": t.text = "非密"
            if value == "年" and e.tag == q("tbl"): t.text = ""
            if "2025年" in value: t.text = value.replace("2025年", "2026年")
        for highlight in e.findall(".//w:highlight", NS): highlight.getparent().remove(highlight)


evidence = json.loads((ROOT / "dist/plancoder-evidence.json").read_text(encoding="utf-8"))
checks = json.loads((ROOT / "dist/selftest-results.json").read_text(encoding="utf-8"))
catalog = json.loads((ROOT / "dist/catalog.json").read_text(encoding="utf-8"))
contract = json.loads((WORK / "template-evidence.json").read_text(encoding="utf-8"))
for source in contract:
    if hashlib.sha256(Path(source["path"]).read_bytes()).hexdigest() != source["sha256"]: raise RuntimeError("模板已变化")
T2 = WORK / "attachment2-reference.docx"
T3 = Path(contract[1]["path"])
manifests = []


def annual_report():
    p = Package(T2)
    cover = copy.deepcopy(p.original[8:26])
    cover[3] = p.p(11, "2026年度重点实验室自主科研任务年度进展报告", title=True)
    # 保留单位等原空白填写区域，不填写未提供的基本信息。
    clean_cover(cover)
    for e in cover:
        for br in e.findall('.//w:br[@w:type="page"]', NS): br.getparent().remove(br)
        for section in e.iter(q("sectPr")):
            kind = section.find("w:type", NS)
            if kind is None: kind = etree.SubElement(section, q("type"))
            kind.set(q("val"), "nextPage")
    sections = [
        ("1.总体情况", [
            "本报告汇总PlanCoder技术分项的年度进展，供中期检查汇总。已形成论文稿、计划驱动代码生成与修复方法、研究代码及两模型四数据集实验记录，并补充指标规则展示与接口。项目基本信息和经费本次不填写。",
            "研究围绕自然语言计划如何影响代码正确性与生成稳定性展开：比较计划提示方式，分析可行性、需求相关性和清晰度三个维度，并据此构建公开测试引导的计划修复和计划条件化检索修复流程。现有实现与论文三阶段流程基本对应。",
            "技术自查表明，本分项已具备研究结果展示、指标和规则接口演示能力。合同目标是否全部达成仍需按正式协议逐项核定；本报告不预填项目级通过结论。论文为现有稿件，尚未提供录用证明；专家现场测试及签字记录尚待完成。",
        ]),
        ("2.本年度项目立项情况", [
            "本分项技术方向为面向代码生成的计划质量评价与质量反馈修复。研究目标是识别有效计划的可观察特征，将可见测试和明确质量准则用于计划优化，并通过计划条件化检索支持剩余代码错误的修复。正式立项信息、协议编号和任务起止时间留空。",
            "年度技术产出包括：论文《What Makes a Good Plan for Effective Code Generation?》稿件；PlanCoder三阶段生成与修复方法及Python实现；可复算的历史结果索引；新增4项指标条目、3条风险预测假设和3条修复策略的展示与接口。现有目录配置的10项指标、5种规则是项目层面的目标参考，不作为本分项已经达标的依据。",
        ]),
        ("3.本年度任务的检查评估情况", [
            "按照2026年9月15日会议纪要的节点安排，检查准备包括报告及成果支撑材料整理、节点自评估、性能指标外部专家测试，以及评审意见闭环。会议纪要要求附件2严格采用甲方模板，附件3可作为参考，并要求评审专家落实回避原则。",
            "本次已开展代码静态核对、历史记录复算、接口及浏览器函数自测。Python检查24项、JavaScript检查6项均通过。该结果属于本机内部自测，不能代替外部专家测试或项目验收结论。整体任务的评估组织情况与正式结论由总体单位汇总。",
        ]),
        ("4.本年度开展项目的检查评估情况", [
            "研究实现采用统一数据适配和运行入口，覆盖MBPP-ET 500题、APPS 139题、CodeContests 150题和LiveCodeBench 140题，每个方法与模型组合共929题。对现有32份完整结果文件进行了按任务编号的复算与来源哈希登记。",
            "数据核对发现：LPW在gpt-5.6-luna的LiveCodeBench文件中存在重复任务，本次统一保留文件中最后一条记录；PlanCoder与LPW的luna CodeContests文件包含多次运行合并信息，原始选择规则仍需核查。部分失败调用的调用量记录为零，成本解释须保留这一限制。上述问题保留原始记录，不以成败选优方式修订结果。",
            "当前检索模型目录缺失，完整生成实验需补齐权重并显式要求检索成功。RQ1五次采样、RQ2逐例评分与人工盲评、消融及检索对照的完整源脚本和原始记录仍待归档。整改安排是补齐原始记录、明确去重及合并口径，并将外部专家复核结果纳入正式材料。",
        ]),
        ("5.本年度取得的年度成果及应用情况", [
            "一是形成计划质量研究结果。论文比较五种提示设置，报告可见测试引导的简洁计划具有较好的正确性与稳定性；在202个配对任务的404份计划上，报告可行性、相关性和清晰度与代码测试通过率的Pearson相关系数分别为0.293、0.198和0.102。上述RQ1、RQ2数值按论文报告引用，当前未独立复算其原始数据。",
            "二是形成PlanCoder方法与代码。阶段一依据任务与公开测试生成计划和代码；阶段二在公开测试失败时按质量准则修复计划并重新生成代码，最多5次；阶段三用最终计划检索和重排参考案例，固定计划与案例进行最多6次代码修复。包含初次生成时最多产生12次代码候选，公开测试通过后停止修复，再评估完整测试。",
            "三是形成对比实验记录。历史记录复算显示，PlanCoder在gpt-5.4-mini上的四数据集通过率为73.4%、70.5%、40.0%、79.3%，宏平均65.8%；在gpt-5.6-luna上分别为75.4%、86.3%、60.0%、85.7%，宏平均76.9%。与最强基线宏平均相比，分别约提高4.4和5.0个百分点。这些是历史记录复算结果，不能解释为本次重新运行或消除合并来源问题后的独立验证。",
            "四是完成成果入库与接口补充。新增S-I01至S-I03计划可行性、相关性和清晰度评分，S-I04同题通过率方差；新增S-R01至S-R03低评分风险假设，以及S-R04至S-R06分阶段修复策略。页面保留PULSE原有8项指标、6条风险条件；汇总为12项指标候选与12条规则或策略条目，质量评分、同源指标与参数化规则族分别说明，独立合同计数待核定。",
            "五是提供应用基础。现阶段可用于独立Python编程任务的计划检查、研究对照、生成稳定性分析和修复阶段演示。尚无实际业务部署或跨模块工程验证材料，不将研究结果表述为已经完成工程应用或形成特定应用效益。",
        ]),
        ("6.组织管理情况", [
            "本分项按论文、代码、原始结果、指标规则定义和测试记录建立证据对应关系。新增目录条目保留来源、输入、计算口径、函数入口、研究证据、限制与核定状态；历史结果索引记录文件SHA-256。文档与代码保留版本和构建脚本，便于复核。",
            "正式检查前需落实成果归属与查重、专家回避及签字。论文录用、报告评审和外部专家测试须分别提供真实证明。单位层面管理制度未提供，本稿不代填。",
        ]),
        ("7.翌年工作考虑", [
            "优先补齐计划评分、人工盲评和消融原始记录，固定评分器、提示词与实现版本，复核弱相关信号在独立任务上的预测价值。为低质量风险规则确定预先固定阈值，报告区分能力和误报漏报，而不是直接将质量分数变换为失败概率。",
            "继续规范检索池去重、检索模型准备、预算和测试超时设置，保留完整运行配置与调用成本；在独立任务及不同模型上复核修复和检索收益。工程扩展可研究模块依赖、接口约束与计划一致性，但应另行设计验证。",
        ]),
        ("8.存在问题及意见建议", [
            "一是项目协议原文及独立条目计数口径尚未纳入本分项材料，建议建立协议指标与证据的逐项对应表。二是论文相关性结论和人工一致性分析缺少当前可直接复算的原始数据，建议优先归档。三是历史结果含重复与合并来源，建议提交明确的数据整理规则及原始运行对照。",
            "四是统一方法表述并独立验证风险阈值，策略与预测规则分列。五是补齐专家测试、录用证明及正式结论。",
        ]),
    ]
    nodes = cover
    for heading, paragraphs in sections:
        nodes.append(p.p(26, heading, heading=True))
        nodes.extend(p.p(27, value) for value in paragraphs)
    final_section = p.section(42)
    final_section.find("w:pgNumType", NS).set(q("start"), "2")
    kind = final_section.find("w:type", NS)
    if kind is None: kind = etree.SubElement(final_section, q("type"))
    kind.set(q("val"), "nextPage")
    p.reset(nodes, final_section)
    manifests.append(p.write(OUT / "01_年度进展报告_PlanCoder技术分项.docx"))


def self_assessment():
    p = Package(T2); nodes = copy.deepcopy(p.original[:6])
    nodes[0] = p.p(0, "2026年度重点实验室自主科研任务协议", title=True)
    nodes[1] = p.p(1, "节点自评估意见", title=True)
    nodes[2] = p.p(2, "本稿整理PlanCoder技术分项的事实与待核事项，供专家审定。评审组织单位、评审时间、评估结论及专家签字留空；不预先表述已经召开评审或已经通过。")
    table = copy.deepcopy(nodes[3]); rows = table.findall("w:tr", NS)
    for height in table.findall(".//w:trHeight", NS): height.getparent().remove(height)
    for row in rows:
        cells = row.findall("w:tc", NS)
        if not cells: continue
        label = re.sub(r"\s+", "", text(cells[0]))
        if label == "评估结论":
            for c in cells[1:]: set_cell(c, "")
        elif label == "具体意见":
            value = ("1.技术成果情况\n已形成计划质量研究论文稿、PlanCoder三阶段方法及研究代码、两模型四数据集历史实验记录，并补充4项指标、3条风险假设和3条修复策略的展示及接口。Python24项和JavaScript6项内部检查通过。\n"
                "2.待复核事项\n正式协议指标与成果计数需核定；RQ1、RQ2和人工盲评原始记录、历史结果合并选择规则需补齐；当前检索模型权重未恢复。论文录用证明、报告评审与外部专家测试记录尚未提供。\n"
                "3.组织管理情况\n已建立代码、目录定义、结果哈希及自测记录的对应索引。单位层面管理制度的执行情况由承担单位另行填写。\n"
                "4.经费意见\n\n专家综合意见及建议\n\n")
            for c in cells[1:]: set_cell(c, value)
        else:
            for c in cells:
                if "专家组组长" in text(c): set_cell(c, "专家组组长签字：\n年    月    日")
    nodes[3] = table
    nodes[4] = p.p(4, "节点自评估专家组组成表", heading=True)
    etree.SubElement(nodes[4].find("w:pPr", NS), q("pageBreakBefore"))
    clean_cover(nodes)
    p.reset(nodes, p.section(42))
    manifests.append(p.write(OUT / "02_节点自评估意见_供专家审定.docx"))


SCENARIOS = [
    {"id": "PC-T01", "name": "目录查询与成果类型核对", "object": "指标库 规则库 展示页面与查询接口", "method": "目录审查、HTTP接口测试和页面操作核对", "data": "catalog.json；4项PlanCoder指标、3条风险假设、3条策略；PULSE原8项指标6条规则。",
     "steps": "1.启动server.py，查询health和完整目录。\n2.按来源筛选PlanCoder和PULSE。\n3.查看类型、证据、函数及计数说明。", "expected": "1.服务正常并返回UTF-8 JSON。\n2.PlanCoder为4项指标6条规则；PULSE为8和6。\n3.预测假设与修复策略区分，链接可访问。", "actual": "1.health返回200与ok。\n2.来源筛选自动检查通过。\n3.目录函数导出一致性检查通过。"},
    {"id": "PC-T02", "name": "计划质量评分与方差计算", "object": "S-I01至S-I04 评分记录校验与计算接口", "method": "确定输入复算与非法输入边界测试", "data": "带评分理由和来源的合成评分记录；通过率[0,0.5,1,0.5,0.5]及[0,0]。",
     "steps": "1.提交三维评分记录并核对来源。\n2.计算两组通过率方差。\n3.提交越界、NaN、单样本或缺来源输入。", "expected": "1.分数不被伪造或解释为概率。\n2.总体方差分别为0.1与0。\n3.非法输入被拒绝，API返回400。", "actual": "1.三维评分记录测试通过。\n2.两组方差与预期一致。\n3.Python和JS边界测试通过。"},
    {"id": "PC-T03", "name": "风险条件及修复阶段边界", "object": "S-R01至S-R06及阶段决策接口", "method": "阈值等值测试与阶段边界测试", "data": "评分0.59和0.6，阈值0.6；公开测试通过标记与计划修复0/5、代码修复0/6组合。",
     "steps": "1.检查低评分条件的严格小于关系。\n2.检查计划修复、检索修复和停止。\n3.检查负数、布尔次数和超预算输入。", "expected": "1.0.59触发，0.6不触发。\n2.四类阶段动作符合定义，默认最多12次代码生成。\n3.非法次数被拒绝。", "actual": "1.阈值等值及缺失测试通过。\n2.阶段与零预算边界通过。\n3.非法次数检查通过。"},
    {"id": "PC-T04", "name": "历史实验结果及证据追溯", "object": "论文RQ3.1对应历史结果与证据索引", "method": "JSONL逐任务去重、统计复算与SHA-256核对", "data": "32份历史完整结果；每组合929个唯一任务。包含已识别的重复记录与合并来源。",
     "steps": "1.按task_id保留最后一条并排除summary。\n2.复算各模型和数据集结果及成本。\n3.核对哈希、重复和合并记录。", "expected": "1.各方法任务数分别为500/139/150/140。\n2.PlanCoder宏平均为65.8%和76.9%。\n3.异常显式保留，不按成败选优。", "actual": "1.32份记录均已索引。\n2.历史结果复算与论文主表取整一致。\n3.重复及合并问题已记录待核。"},
    {"id": "PC-T05", "name": "评分服务配置与错误响应", "object": "真实模型评分接口及API异常处理", "method": "关闭模型配置下的接口测试及评分输入隔离检查", "data": "合成任务计划；缺少评分配置、未知条目、错误JSON或媒体类型、跨源请求。",
     "steps": "1.未配置模型时请求真实评分。\n2.检查三维提示的输入隔离。\n3.提交未知条目及非法请求。", "expected": "1.返回503，不以演示值冒充真实评分。\n2.相关性与清晰度不接收测试。\n3.按场景返回400/404/415/403。", "actual": "1.未配置测试返回503。\n2.三维提示隔离检查通过。\n3.错误状态码检查通过。真实外部模型调用未执行。"},
]


def case_table(p, case, report=False):
    values = {"场景编号": case["id"], "场景名称": case["name"], "场景描述": "PlanCoder技术分项本地验证；正式专家测试地点、单位及人员留空。", "测试对象及考核指标": case["object"],
        "测试环境": "Windows本地环境；Python标准库服务；Node.js浏览器函数测试；localhost访问。", "测试设备": "本机开发工作站；正式专家测试设备编号留空。", "测试方法": case["method"], "测试数据": case["data"],
        "测试要求": "固定版本与输入，保存输出及哈希；合成样例和历史记录分开说明，不访问隐藏测试作为预测输入。", "测试流程": [case["steps"], case["expected"]] + ([case["actual"]] if report else []),
        "合格判据": "所列步骤结果符合预期且异常边界被正确处理；历史结果可追溯。项目级达标由协议对照及专家审定。", "备注": "内部检查不替代专家签字；风险阈值仅为合成演示，不代表已验证预测阈值。"}
    if report:
        values.update({"实际结果与预期结果对比": "内部自测：所列已执行检查与预期一致。\n专家现场复核：", "总体测试结论": "内部自测检查通过。\n专家现场结论：", "测试专家/时间": ""})
    return fill_table(p.original[98 if report else 42], values)


def blank_cover_table(table):
    clone = copy.deepcopy(table)
    for row in clone.findall("w:tr", NS):
        cells = row.findall("w:tc", NS)
        for i, c in enumerate(cells):
            if i % 2: set_cell(c, "")
    return clone


def test_outline():
    p = Package(T3)
    cover = copy.deepcopy(p.original[:13]); cover[4] = p.p(4, "PlanCoder项目测试检验大纲", title=True); cover[7] = blank_cover_table(cover[7]); clean_cover(cover)
    # 目录采用模板段落，去除示例页码；保留目录和正文分节。
    nodes = cover + [p.p(13, "目  录")]
    for value in ("一 测试目的", "二 测试依据", "三 测试检验总体方案", "四 测试场景设置", "五 风险分析与防范措施", "附表 项目测试检验总体安排", "子附件 测试大纲评审意见与专家组成表"):
        nodes.append(p.p(14, value))
    nodes.append(copy.deepcopy(p.original[22]))
    content = [
        ("一 测试目的", ["对PlanCoder技术分项形成的指标定义、规则条件函数、展示页面、HTTP接口及历史结果索引开展可重复测试，为中期检查提供技术依据。测试范围为当前可核查成果，不代替项目全部合同指标覆盖性审查。项目协议基本信息和经费本次留空。", "三项计划质量评分是质量信号；通过率方差是结果波动量；低评分规则为预测假设；三阶段控制为修复策略。测试需确认这些类型与证据状态被正确区分，不将分数或布尔标记解释为校准后的失败概率。"]),
        ("二 测试依据", ["依据甲方下发附件2的文档结构、附件3测试大纲与测试报告参考模板，以及2026年9月15日会议纪要提出的成果、节点、专家回避和支撑材料要求编制。技术依据为现有论文稿、PlanCoder研究实现、原有指标规则目录和本次接口实现。", "正式协议及其考核原文未在本次填写范围内。现有页面配置的指标不少于10项、规则不少于5种仅作目标参考，须由项目组结合协议复核；本分项不以候选数量推定合同达标。"]),
        ("三 测试检验总体方案", ["测试对象包括指标与规则条目、可调用计算和条件函数、本地展示与接口、历史结果证据四类。设计五种场景：目录与类型核对、评分和方差计算、规则与阶段边界、历史结果复算、评分配置与错误处理。各项先完成内部自测，再由项目组按协议确定外部测试组织方式。", "当前建议采用专家复核与现场操作演示，对数学口径、规则类型、证据来源和复算程序进行联合检查。这些对象包含模型评分输入边界与研究证据判读，仅凭页面数量或单次接口调用不足以评价。是否采用专家测试以及具体专家、地点、日期由项目组确认；本稿不虚构已安排的第三方机构。", "专家应按会议纪要落实回避原则，不得包括项目牵头单位及本单位专家。正式测试前固定软件版本、测试数据、日志与哈希，准备独立运行环境；全过程保留实际结果、异常与专家签字。真实外部模型评分为可选配置项，本轮内部自测未发起模型调用，不将其列为已完成性能验证。"]),
        ("四 测试场景设置", ["场景PC-T01至PC-T05分别检验目录完整性、指标计算与来源要求、条件与预算边界、历史记录可追溯性，以及模型配置和异常响应。确定性函数用合成输入检验；研究效果通过原始结果复算与专家复核检验，两者不混同。"]),
    ]
    for heading, paras in content:
        nodes.append(p.p(23, heading.split(" ", 1)[1], heading=True)); nodes.extend(p.p(24, value) for value in paras)
    for case in SCENARIOS:
        nodes.append(pagebreak(p, 24)); nodes.append(p.p(41, case["id"] + " " + case["name"], heading=True)); nodes.append(case_table(p, case)); nodes.append(p.p(43, ""))
    nodes.append(pagebreak(p, 24)); nodes.append(p.p(44, "风险分析与防范措施", heading=True))
    risks = ["数据风险：原始结果含重复和多次运行合并。固定按任务编号保留最后记录，不以成败选优；保留合并来源待核项与所有原文件哈希。", "证据风险：论文部分分析的原始数据尚未提供。将论文报告值与已复算值分开；未取得录用证明或专家签字时不写已录用或已通过。", "配置风险：当前研究目录缺少检索模型权重。完整生成复现实验应补齐权重并要求检索成功，避免auto降级被误认为完整方法。", "评价风险：质量评分阈值未独立验证，部分维度相关性较弱。演示阈值显式标注，预测假设与响应策略分列，不以函数测试通过替代预测有效性。", "环境风险：不同方法的测试超时与重试策略可能影响成本和通过率。正式独立复核应统一或明确报告这些配置；本次仅对历史记录重新统计。"]
    nodes.extend(p.p(24, value) for value in risks)
    nodes.append(pagebreak(p, 24)); nodes.append(p.p(50, "项目测试检验总体安排", heading=True))
    overview = copy.deepcopy(p.original[51]); rows = overview.findall("w:tr", NS)
    for i, row in enumerate(rows[1:]):
        cells = row.findall("w:tc", NS)
        values = ([str(i+1), SCENARIOS[i]["object"], SCENARIOS[i]["name"], "拟由专家复核", "", SCENARIOS[i]["id"]] if i < 5 else ["", "", "", "", "", ""])
        for cell, value in zip(cells, values): set_cell(cell, value)
    nodes.append(overview)
    nodes.append(p.p(24, "表内时间、地点、专家组织信息留空；正式测试方式以协议和项目组安排为准。内部自测记录见配套报告，五场景与接口测试记录逐项对应。"))
    nodes.append(pagebreak(p, 24)); nodes.append(p.p(59, "项目测试检验大纲评审意见", title=True))
    review = blank_cover_table(p.original[60])
    for row in review.findall("w:tr", NS):
        for cell in row.findall("w:tc", NS):
            if "20XX" in text(cell) or "同意通过" in text(cell): set_cell(cell, "评审意见：\n\n\n\n\n")
    nodes.append(review)
    nodes.append(pagebreak(p, 24)); nodes.append(p.p(61, "专家组组成表", heading=True)); nodes.append(copy.deepcopy(p.original[62]))
    p.reset(nodes, p.section(63)); manifests.append(p.write(OUT / "03_PlanCoder项目测试检验大纲.docx"))


def test_report():
    p = Package(T3)
    cover = copy.deepcopy(p.original[64:77]); cover[5] = p.p(69, "PlanCoder项目测试检验报告", title=True); cover[6] = p.p(70, "内部自测版  专家测试栏留空"); cover[8] = blank_cover_table(cover[8]); clean_cover(cover)
    nodes = cover + [p.p(77, "目  录")]
    for value in ("一 测试情况概述", "二 测试情况", "三 测试结论", "附表一 内部自测场景记录", "附表二 专家现场测试记录及专家组成表"):
        nodes.append(p.p(78, value))
    nodes.append(copy.deepcopy(p.original[84]))
    nodes.append(p.p(85, "一 测试情况概述", heading=True))
    paras = ["本报告记录2026年10月22日针对PlanCoder技术分项实施的本机内部自测和历史结果复算，采用配套测试大纲PC-T01至PC-T05场景。项目基本信息和经费留空。未组织外部专家现场测试，不预填专家到场、评审通过或合同验收结论。",
        f"自测环境为{checks['environment']['system']} {checks['environment']['release']} {checks['environment']['machine']}，Python {checks['python']['version']}，Node.js {checks['javascript']['version']}。接口由Python标准库提供，测试访问本机回环地址；真实外部模型调用未执行。测试执行时间与源文件哈希保存于dist/selftest-results.json。",
        "测试依据为配套测试大纲、论文稿、PlanCoder研究实现、本次目录及接口源码。论文RQ1、RQ2和人工一致性数值按论文报告引用，当前未取得相应原始记录，不列为本次已经验证的统计结果。正式专家测试组织、时间地点、评审意见与签字均留待实际执行。"]
    nodes.extend(p.p(86, value) for value in paras)
    nodes.append(p.p(91, "二 测试情况", heading=True))
    paras = ["执行Python单元与HTTP接口检查24项，全部通过；执行JavaScript函数与既有PULSE回归检查6项，全部通过。覆盖三维评分来源校验、总体方差、非法输入、阈值边界、修复预算、目录来源筛选、模型未配置响应、JSON和媒体类型错误、跨源请求拒绝及OpenAPI和证据查询。",
        "确定输入的结果包括：通过率[0,0.5,1,0.5,0.5]的总体方差为0.1，[0,0]的方差为0；评分0.59在阈值0.6时触发，评分0.6不触发；初始失败进入计划修复，5次计划修复耗尽进入检索修复，6次代码修复耗尽后返回最终代码；公开测试通过时直接返回并评估隐藏测试。",
        "目录保留原PULSE 8项指标和6条风险条件，新增PlanCoder 4项指标、3条风险假设和3条修复策略。共展示12项指标候选与12条规则或策略，均保留研究来源、类型、接口、证据和限制。目录条目数量与独立合同计数分别处理。",
        "历史结果核查覆盖32份完整结果文件。每个方法与模型组合为500/139/150/140题；PlanCoder宏平均通过率分别为65.8%和76.9%。逐文件指标、耗时、调用量、哈希与待核问题保存在dist/plancoder-evidence.json。该检查未重新运行生成代码、未重新调用模型，验证的是保存记录及统计口径。",
        "发现LPW luna LiveCodeBench文件有141条任务记录但仅140个唯一任务，其中重复任务结果不同；按最后记录保留后通过率为81.43%，与论文81.4%取整一致。PlanCoder与LPW luna CodeContests文件含合并来源；部分失败调用记录的调用量为零。上述问题已显式登记，不能据此宣称单次独立运行的完整可复现性。",
        "真实模型评分在未配置状态下返回503。相关性和清晰度评分提示不接收测试数据，可行性提示接收可见测试。评分接口是本次按论文定义补充的实现，原始论文评分脚本尚未归档；外部评分质量与预测阈值有效性仍需独立验证。"]
    nodes.extend(p.p(86, value) for value in paras)
    nodes.append(pagebreak(p, 86)); nodes.append(p.p(93, "三 测试结论", heading=True))
    nodes.extend(p.p(86, value) for value in ["本机内部自测的24项Python检查与6项JavaScript检查均通过，当前目录、确定性计算、规则条件与阶段决策接口具备本地演示能力；现有PULSE函数通过相关回归检查。", "尚未完成的验证包括：外部专家现场测试、真实外部模型评分质量验证、风险阈值独立验证、RQ1/RQ2及人工盲评原始数据复算、历史结果合并规则核查、检索模型恢复后的完整生成复现。内部检查通过不等于项目合同指标全部达标。", "专家现场测试结论：\n\n专家组组长签字：\n年    月    日"])
    nodes.append(pagebreak(p, 86)); nodes.append(p.p(97, "附表一 内部自测场景记录", heading=True))
    for case in SCENARIOS:
        if case != SCENARIOS[0]: nodes.append(pagebreak(p, 86))
        nodes.append(p.p(91, case["id"] + " " + case["name"], heading=True)); nodes.append(case_table(p, case, True)); nodes.append(p.p(86, ""))
    nodes.append(pagebreak(p, 86)); nodes.append(p.p(97, "附表二 专家现场测试记录表", heading=True))
    blank = fill_table(p.original[98], {
        "测试流程": ["测试步骤\n\n\n\n\n", "预期结果\n\n\n\n\n", "实际结果\n\n\n\n\n"],
        "实际结果与预期结果对比": "逐步骤记录符合情况及偏差\n\n\n",
        "合格判据": "所列步骤均达到预期结果则判定符合；存在偏差时如实记录并由专家判定。",
        "总体测试结论": "□符合    □基本符合    □不符合",
    }, blank=True)
    nodes.append(blank)
    nodes.append(pagebreak(p, 86)); nodes.append(p.p(100, "专家组组成表", heading=True)); nodes.append(copy.deepcopy(p.original[101]))
    p.reset(nodes, p.section(105)); manifests.append(p.write(OUT / "04_PlanCoder项目测试检验报告_内部自测版.docx"))


if __name__ == "__main__":
    if not (WORK / "artifact.md").exists(): raise RuntimeError("缺少模板执行约定")
    annual_report(); self_assessment(); test_outline(); test_report()
    (WORK / "document-build-manifest.json").write_text(json.dumps(manifests, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Created four template-derived DOCX files; preserve-only package parts unchanged.")
