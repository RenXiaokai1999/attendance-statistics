# 因公外出规则扩展与明细登记 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 扩展因公外出分类，并将最终有效的因公外出事项写入旧版 Word 考勤表的第二张登记表。

**Architecture:** 在图片候选层扩展关键词，但继续由人工视觉复核产生结构化记录；在结构化记录中保存事项类别、事由、地点、批准人、同行人与事项标识。归并层同时返回最终生效记录，Word 写入层据此生成第二张表，保证汇总、明细和 Excel 着色同源。

**Tech Stack:** Python 3.12、`unittest`、WPS/Word COM、JSON 复核清单。

---

### Task 1: 扩展因公外出候选分类

**Files:**
- Modify: `scripts/scan_attendance_images.py`
- Test: `tests/test_image_rules.py`

**Step 1: Write the failing test**

增加因公出差、因公外出办事、组织同意培训、水准测量、非组织培训以及普通用车附件的分类边界测试。

**Step 2: Run test to verify it fails**

Run: `py -3.12 -m unittest tests.test_image_rules -v`

Expected: 新增的办事与培训案例失败。

**Step 3: Write minimal implementation**

加入明确的外出办事与组织批准培训关键词判断；保留出差、水准测量规则，并确保只有普通用车关键词时仍为无关候选。

**Step 4: Run test to verify it passes**

Run: `py -3.12 -m unittest tests.test_image_rules -v`

Expected: PASS。

### Task 2: 保存并归并因公外出事项明细

**Files:**
- Modify: `scripts/models.py`
- Modify: `scripts/run_attendance.py`
- Modify: `scripts/reconcile.py`
- Test: `tests/test_pipeline.py`
- Test: `tests/test_reconcile.py`

**Step 1: Write the failing test**

验证复核 JSON 可读取 `official_out_category`、`reason`、`location`、`approver`、`companions`、`event_id`，并验证归并结果只暴露最终有效、无冲突的因公外出记录。

**Step 2: Run tests to verify they fail**

Run: `py -3.12 -m unittest tests.test_pipeline tests.test_reconcile -v`

Expected: 新字段或最终记录接口不存在。

**Step 3: Write minimal implementation**

扩展 `AttendanceRecord` 的可选明细字段；加载复核 JSON 时读取这些字段；在 `ReconcileResult` 中保留每个姓名日期最终生效的原始记录，同时维持现有计数和冲突逻辑。

**Step 4: Run tests to verify they pass**

Run: `py -3.12 -m unittest tests.test_pipeline tests.test_reconcile -v`

Expected: PASS。

### Task 3: 生成去重后的登记表事项

**Files:**
- Modify: `scripts/run_attendance.py`
- Test: `tests/test_pipeline.py`

**Step 1: Write the failing test**

构造同一 `event_id` 下申请人与同行人多日记录，验证输出合并为一个事项，包含起止日期、有效工作日天数和同行人员；不同事项不合并。

**Step 2: Run test to verify it fails**

Run: `py -3.12 -m unittest tests.test_pipeline -v`

Expected: 明细构建函数不存在。

**Step 3: Write minimal implementation**

新增 `OfficialOutDetail` 与明细构建函数，按 `event_id` 优先、稳定来源与事项字段回退分组；申请人作为登记人，其余参与者进入同行备注。缺少可靠事由的记录不进入明细并报告。

**Step 4: Run test to verify it passes**

Run: `py -3.12 -m unittest tests.test_pipeline -v`

Expected: PASS。

### Task 4: 写入旧版 Word 第二张表

**Files:**
- Modify: `scripts/write_attendance_doc.py`
- Test: `tests/test_write_attendance_doc.py`

**Step 1: Write the failing test**

在临时输出中写入两条事项，验证第二张表只保留表头与当月明细，七列内容正确，模板原文件哈希不变；再用超过模板原行数的明细验证自动扩行。

**Step 2: Run test to verify it fails**

Run: `py -3.12 -m unittest tests.test_write_attendance_doc -v`

Expected: 第二张表仍保留7月示例。

**Step 3: Write minimal implementation**

给 `write_attendance_doc` 增加可选明细参数；清除第二张表表头后的内容并按需增删行，写入七列，保留表头和旧版 `.doc` 格式。

**Step 4: Run test to verify it passes**

Run: `py -3.12 -m unittest tests.test_write_attendance_doc -v`

Expected: PASS。

### Task 5: 接入流水线、更新规则并回归验证

**Files:**
- Modify: `scripts/run_attendance.py`
- Modify: `scripts/validate_outputs.py`
- Modify: `SKILL.md`
- Modify: `PROJECT_OVERVIEW.md`
- Modify: `PROJECT_RULES.md`
- Modify: `PROJECT_PROGRESS.md`
- Modify: `references/统计规则.md`
- Modify: `references/图片分类规则.md`
- Test: `tests/test_pipeline.py`
- Test: `tests/test_write_attendance_doc.py`

**Step 1: Write the failing integration test**

验证流水线将归并后的明细传给 Word 写入器，报告记录明细数量和待确认原因。

**Step 2: Run integration tests to verify they fail**

Run: `py -3.12 -m unittest tests.test_pipeline tests.test_write_attendance_doc -v`

Expected: 流水线尚未传递明细。

**Step 3: Implement integration and documentation**

接入明细构建与 Word 验证，更新 Skill、项目规则、统计规则、图片分类规则和自动任务提示词，明确三类因公外出及用车附件边界。

**Step 4: Run full verification**

Run: `py -3.12 -m unittest discover -s tests -v`

Run: `py -3.12 C:\Users\11789\.claude\skills\.system\skill-creator\scripts\quick_validate.py C:\Users\11789\.claude\skills\attendance-statistics`

Expected: 全部测试通过，Skill 校验通过。

**Step 5: Verify a temporary Word output**

在临时目录生成旧版 `.doc`，重新打开并核对第二张表表头、当月明细、总行数以及第一张表统计值；不得覆盖用户当前文件。

