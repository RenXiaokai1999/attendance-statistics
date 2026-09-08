# 所有用车申请全量统计 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将所有正式用车申请无条件纳入因公外出汇总与明细，保留单独即时客运票据排除规则。

**Architecture:** 在图片分类层将正式用车单据作为高优先级因公外出候选；复核记录层不再因未审批、撤回、取消或作废过滤用车申请。现有归并器继续按人员、日期和事项去重，Word与Excel沿用统一最终记录。

**Tech Stack:** Python 3.12、unittest、Pillow、pytesseract、openpyxl、WPS/Word COM

---

### Task 1: 扩大正式用车单据召回

**Files:**
- Modify: `tests/test_image_rules.py`
- Modify: `scripts/scan_attendance_images.py`

1. 增加失败测试：用车申请、用车审批单、派车申请均分类为`official_out`。
2. 增加回归测试：单独出租车发票、打车订单、网约车行程单仍为`irrelevant`。
3. 运行目标测试并确认新用车测试失败。
4. 增加正式用车单据关键词和优先判定。
5. 运行目标测试并确认通过。

### Task 2: 允许所有审批状态的用车申请进入统计

**Files:**
- Modify: `tests/test_reconcile.py`
- Modify: `scripts/models.py`
- Modify: `scripts/reconcile.py`
- Modify: `scripts/run_attendance.py`

1. 增加失败测试：未审批、撤回、取消、作废的正式用车申请仍进入有效因公外出记录。
2. 为复核记录增加可识别的正式用车申请标记，保持旧JSON兼容。
3. 仅对正式用车申请绕过审批和取消状态过滤，其他类型规则不变。
4. 验证多人同日统计、事项明细归并和重复附件去重。

### Task 3: 固化最终Skill规则

**Files:**
- Modify: `SKILL.md`
- Modify: `PROJECT_RULES.md`
- Modify: `PROJECT_OVERVIEW.md`
- Modify: `references/统计规则.md`
- Modify: `references/图片分类规则.md`

1. 写明所有正式用车申请一律先统计，由用户最终手动删除。
2. 写明未审批、撤回、取消、作废同样收录。
3. 写明单独出租车、打车、网约车票据仍不统计。
4. 写明多人汇总、单事项一行和多附件去重规则。

### Task 4: 重扫并复核8月全部用车申请

**Files:**
- Create: `E:\山西省地震局工作\大同台\考勤\测试\所有用车申请全量统计\2026年8月\图片复核清单_全部用车.json`
- Create: `E:\山西省地震局工作\大同台\考勤\测试\所有用车申请全量统计\2026年8月\已复核记录_全部用车.json`

1. 扫描2026年7月、8月、9月图片缓存。
2. 筛选全部正式用车申请并逐张确认日期、申请人、使用人、事由和地点。
3. 将未审批、撤回、取消、作废的正式用车申请同样写入已复核记录。
4. 与既有记录按事项、人员、日期归并去重。
5. 日期或人员不清的项目写入人工确认清单。

### Task 5: 生成并验证8月最终测试版

**Files:**
- Create: `E:\山西省地震局工作\大同台\考勤\测试\所有用车申请全量统计\2026年8月\202608DTZ考勤表.doc`
- Create: `E:\山西省地震局工作\大同台\考勤\测试\所有用车申请全量统计\2026年8月\签卡记录2026-08-01到2026-08-31_考勤标注.xlsx`
- Create: `E:\山西省地震局工作\大同台\考勤\测试\所有用车申请全量统计\2026年8月\202608考勤运行报告.json`

1. 复制原始签卡表和最新已复核数据到新测试目录。
2. 运行8月统计流程。
3. 重新读取Word，核对因公外出汇总和全部用车明细。
4. 重新读取Excel，核对有打卡无底色、无打卡因公外出深蓝色。
5. 对比两次原始签卡只读副本哈希，确认原件未修改。

### Task 6: 全量验证并同步定时任务

**Files:**
- Modify: `PROJECT_PROGRESS.md`
- Update: Codex automation `automation-2`

1. 运行`py -3.12 -m unittest discover -s tests -q`，预期全部通过。
2. 运行Skill快速校验，预期`Skill is valid!`。
3. 检查运行报告中的冲突、待确认项和固定水准日期。
4. 更新每月1日15:00定时任务提示词为最终用车规则。
5. 更新进展日志并报告输出路径与统计变化。
