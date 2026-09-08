# 租车纳入因公外出 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将日期和人员明确的租车材料计入因公外出，并排除出租车、打车和网约车。

**Architecture:** 在图片OCR分类层增加“租车正向词+即时客运排除词”的优先判定，复核后继续生成现有`official_out`记录。通过测试驱动修改分类逻辑，再重扫三个月图片、人工复核候选并在独立目录生成8月结果。

**Tech Stack:** Python 3.12、unittest、Pillow、pytesseract、openpyxl、WPS/Word COM

---

### Task 1: 锁定租车分类边界

**Files:**
- Modify: `tests/test_image_rules.py`
- Modify: `scripts/scan_attendance_images.py`

1. 增加失败测试：`租车合同`、`车辆租赁发票`、`汽车租赁明细`分类为`official_out`。
2. 增加失败测试：`出租车发票`、`打车订单`、`网约车行程单`保持`irrelevant`。
3. 运行目标测试，确认因缺少租车规则而失败。
4. 增加租车正向词和即时客运排除词；排除词优先。
5. 运行目标测试，确认通过。

### Task 2: 固化复核与归并规则

**Files:**
- Modify: `PROJECT_RULES.md`
- Modify: `SKILL.md`
- Modify: `references/统计规则.md`
- Modify: `references/图片分类规则.md`

1. 写明租车材料不要求另有审批截图，只要日期和人员明确即可统计。
2. 写明只有承租人时只计承租人，不推测同行人员。
3. 写明日期或人员不清时进入人工确认。
4. 写明同一事项多张附件归并去重。

### Task 3: 重扫并复核8月租车候选

**Files:**
- Create: `E:\山西省地震局工作\大同台\考勤\测试\租车纳入因公外出\2026年8月\图片复核清单_租车规则.json`
- Create: `E:\山西省地震局工作\大同台\考勤\测试\租车纳入因公外出\2026年8月\已复核记录_租车规则.json`

1. 扫描2026年7月、8月、9月图片缓存。
2. 筛出租车正向候选，并剔除出租车、打车、网约车。
3. 逐张确认租车日期、承租人和明确列出的用车人员。
4. 与现有已复核记录按事项、人员、日期去重。
5. 日期或人员不清的材料写入待确认项，不自动填写。

### Task 4: 生成8月独立测试结果

**Files:**
- Create: `E:\山西省地震局工作\大同台\考勤\测试\租车纳入因公外出\2026年8月\202608DTZ考勤表.doc`
- Create: `E:\山西省地震局工作\大同台\考勤\测试\租车纳入因公外出\2026年8月\签卡记录2026-08-01到2026-08-31_考勤标注.xlsx`
- Create: `E:\山西省地震局工作\大同台\考勤\测试\租车纳入因公外出\2026年8月\202608考勤运行报告.json`

1. 复制原始签卡表和最新已复核JSON到新测试目录。
2. 运行8月统计流程。
3. 重新读取Word，核对因公外出汇总和明细。
4. 重新读取Excel，核对有打卡无底色、无打卡租车日期深蓝色。
5. 对比原始签卡表哈希，确认原件未修改。

### Task 5: 全量验证并同步定时任务

**Files:**
- Modify: `PROJECT_PROGRESS.md`
- Update: Codex automation `automation-2`

1. 运行`py -3.12 -m unittest discover -s tests -q`，预期全部通过。
2. 运行Skill快速校验，预期`Skill is valid!`。
3. 检查运行报告中的冲突、待确认项和固定水准日期。
4. 更新每月1日15:00定时任务提示词，加入租车正向规则和出租车/打车/网约车排除规则。
5. 更新进展日志，报告新输出路径和统计变化。
