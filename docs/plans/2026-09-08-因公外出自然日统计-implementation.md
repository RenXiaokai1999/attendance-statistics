# 因公外出自然日统计 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将因公外出改为工作日、周末和法定节假日全部按自然日统计，并修复水准测量候选漏检。

**Architecture:** 复核记录直接保存目标月内全部自然日，不再由工作日日历裁剪因公外出。图片扫描采用多关键词和双版面OCR取并集，只对完全相同文件去重；归并后的同一批记录驱动 Word 汇总、Word 明细和 Excel 着色。

**Tech Stack:** Python 3.12、Tesseract OCR、`unittest`、WPS/Word COM、openpyxl。

---

### Task 1: 固化自然日统计规则

**Files:**
- Modify: `scripts/run_attendance.py`
- Modify: `scripts/models.py`
- Test: `tests/test_pipeline.py`
- Test: `tests/test_reconcile.py`

**Steps:**
1. 新增跨周末及法定节假日的因公外出测试，期望所有目标月自然日都进入汇总和明细。
2. 运行目标测试，确认旧逻辑或旧数据约束不能满足。
3. 实现目标月自然日展开与边界裁剪，因公外出不调用工作日过滤。
4. 运行目标测试并确认通过。

### Task 2: 提高水准测量候选召回率

**Files:**
- Modify: `scripts/scan_attendance_images.py`
- Test: `tests/test_image_rules.py`

**Steps:**
1. 增加“水准观测记录手簿”“水准观测”“水准作业”及表格小字图片的失败测试。
2. 扩展关键词，OCR使用 `--psm 6` 与 `--psm 11` 结果并集。
3. 保留SHA-256完全重复去重，取消分类前的感知哈希淘汰。
4. 运行图片规则测试并确认通过。

### Task 3: 同步Word明细与Excel状态

**Files:**
- Modify: `scripts/write_attendance_doc.py`
- Modify: `scripts/annotate_punch_workbook.py`
- Modify: `scripts/validate_outputs.py`
- Test: `tests/test_write_attendance_doc.py`
- Test: `tests/test_annotate_punch_workbook.py`

**Steps:**
1. 增加周末、法定节假日明细天数及Excel深蓝色测试。
2. 确保明细显示原始起止日期和自然日数。
3. 保持“有打卡则无底色并提醒”的优先级。
4. 运行Word与Excel测试并确认通过。

### Task 4: 更新规则与自动任务

**Files:**
- Modify: `SKILL.md`
- Modify: `PROJECT_RULES.md`
- Modify: `PROJECT_OVERVIEW.md`
- Modify: `PROJECT_PROGRESS.md`
- Modify: `references/统计规则.md`
- Modify: `references/图片分类规则.md`

**Steps:**
1. 将因公外出“按国家工作日”统一改为“按自然日”。
2. 写明工作日、周末、法定节假日全部计入及OCR召回规则。
3. 更新现有每月自动任务提示词。

### Task 5: 重跑2026年8月独立测试版

**Files:**
- Create: `E:\山西省地震局工作\大同台\考勤\测试\因公外出自然日规则\2026年8月\*`

**Steps:**
1. 复核并补录8月1日、8月16日等周末水准测量事项。
2. 复制原始签卡文件到新测试目录，不覆盖原件。
3. 生成 Word、Excel和运行报告。
4. 重新打开产物，核对自然日汇总、明细、颜色、待确认项和原文件哈希。
5. 运行 `py -3.12 -m unittest discover -s tests -v`。
6. 运行 Skill 结构校验。
