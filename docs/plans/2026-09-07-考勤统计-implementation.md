# Attendance Statistics Skill Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 创建可自动或手动运行的本地考勤统计 Skill，生成 `.doc` 月度考勤表和带状态颜色的 `.xlsx` 签卡记录。

**Architecture:** Skill 负责流程编排和需要判断的图片复核；Python 模块负责确定性解析、归并、Word/Excel 写入和验证。所有来源先转换为统一记录，再执行去重、审批、冲突和月份归属规则。

**Tech Stack:** Python 3.12 标准库、openpyxl、pywin32、Pillow、pytesseract、Microsoft Word COM、Codex CDP 浏览器、Windows 凭据管理器、unittest。

---

### Task 1: 创建 Skill 骨架与配置

**Files:**
- Create: `SKILL.md`
- Create: `config/settings.json`
- Create: `references/统计规则.md`
- Test: `tests/test_config.py`

**Steps:**
1. 编写失败测试，验证目标月份、月份目录名、文件名和源目录路径计算。
2. 运行 `python -m unittest tests.test_config -v`，确认失败。
3. 实现月份上下文和配置加载，不写入任何凭据。
4. 编写 `SKILL.md`，定义触发语句、自动/手动运行流程、所需输入和异常终止条件。
5. 运行测试，确认路径示例与2026年8月完全一致。

### Task 2: Windows 凭据管理器

**Files:**
- Create: `scripts/credentials.py`
- Create: `scripts/setup_credentials.py`
- Test: `tests/test_credentials.py`

**Steps:**
1. 编写测试，验证配置仅包含凭据目标名称，不含用户名或密码。
2. 使用 `win32cred.CredRead/CredWrite` 实现首次保存和运行时读取。
3. 确保任何异常消息只显示凭据名称，不显示秘密内容。
4. 运行测试并扫描项目文件，确认没有明文凭据。

### Task 3: 统一数据模型、姓名和日期规则

**Files:**
- Create: `scripts/models.py`
- Create: `scripts/normalize.py`
- Create: `scripts/work_calendar.py`
- Create: `references/法定节假日数据说明.md`
- Test: `tests/test_normalize.py`
- Test: `tests/test_work_calendar.py`

**Steps:**
1. 定义统一记录：姓名、日期、类型、来源、审批状态、是否整天、版本时间和置信度。
2. 编写姓名空格、全半角和不可见字符清理测试。
3. 编写法定假期、正常周末、调休上班周末测试。
4. 实现读取年度官方放假安排缓存的工作日判断；缺少当年数据时停止并提示更新。
5. 运行测试，覆盖跨月和月末日期。

### Task 4: 下载和解析签卡记录

**Files:**
- Create: `scripts/download_punch_records.py`
- Create: `scripts/parse_punch_records.py`
- Test: `tests/test_parse_punch_records.py`

**Steps:**
1. 使用本地 CDP 浏览器测试登录页和打卡记录页的实际控件、下载行为及文件名。
2. 登录信息从 Windows 凭据管理器读取，禁止写入命令输出。
3. 下载到当月目录并验证日期范围、扩展名和工作表结构。
4. 编写测试，验证同一人员一天多次打卡只计1个出勤日。
5. 实现 Excel 表头、姓名、每日列和打卡时间解析。
6. 运行测试，并确认原始下载文件哈希保持不变。

### Task 5: 解析24h值班零报告

**Files:**
- Create: `scripts/parse_all_day_duty.py`
- Test: `tests/test_parse_all_day_duty.py`

**Steps:**
1. 使用 Word COM 只读打开每日 `.doc`，提取报告日期和“填报人”。
2. 编写测试覆盖完整月份、缺失日期、空姓名、同日重复和不同姓名冲突。
3. 实现按日期归并；同日不同姓名不计并输出冲突。
4. 对2026年8月31份样例做抽样核对。

### Task 6: 解析数据预处理 HTML

**Files:**
- Create: `scripts/parse_preprocess_html.py`
- Test: `tests/test_parse_preprocess_html.py`

**Steps:**
1. 使用标准库 HTML 解析器读取所有配套分页中的日期和值班员。
2. 编写测试覆盖重复分页、同日冲突和无关顶层 HTML。
3. 结合工作日日历，只保留正常休息性质的自然周六、周日。
4. 验证法定假期内周末和调休上班周末均被排除。

### Task 7: 图片候选提取与人工复核清单

**Files:**
- Create: `scripts/scan_attendance_images.py`
- Create: `scripts/image_review_manifest.py`
- Create: `references/图片分类规则.md`
- Test: `tests/test_image_rules.py`

**Steps:**
1. 扫描目标月及前一个月图片，按文件哈希和感知指纹去重。
2. 使用 Tesseract 提取请假、调休、出差、水准测量、审批、撤回和改期候选。
3. 生成结构化复核清单，保留来源文件，不自动接受低置信度字段。
4. 编写分类测试：补休、非调休请假、出差、水准测量、无关用车、未审批、撤回、跨月和半天。
5. Skill 对候选图片进行视觉复核，输出最终结构化记录和待确认项。

### Task 8: 归并、去重和冲突检测

**Files:**
- Create: `scripts/reconcile.py`
- Test: `tests/test_reconcile.py`

**Steps:**
1. 编写测试覆盖同人同日同类型去重、最新撤回、改期和跨来源重复。
2. 实现只有获批整天记录才进入补休、请假和因公外出统计。
3. 实现半天、小时、低置信度和多状态冲突暂不计入。
4. 实现“打卡与休假/外出并存”提醒。
5. 运行完整规则测试。

### Task 9: 写入旧版 Word 考勤表

**Files:**
- Create: `scripts/write_attendance_doc.py`
- Test: `tests/test_write_attendance_doc.py`

**Steps:**
1. 复制模板到隔离测试目录，禁止修改模板原件。
2. 使用 Word COM 按表头和姓名定位六项统计列，避免依赖固定行号。
3. 无值保持空白；模板外人员追加到名单末尾，其他项目留空。
4. 保存为 `.doc`，重新打开并读取写入值进行验证。
5. 比较模板及其他单元格，确认版式和未授权字段未变。

### Task 10: 生成 Excel 考勤标注表

**Files:**
- Create: `scripts/annotate_punch_workbook.py`
- Test: `tests/test_annotate_punch_workbook.py`

**Steps:**
1. 复制原始签卡记录，不覆盖下载文件。
2. 按姓名和日期定位单元格，保留打卡时间。
3. 实现颜色：因公外出 `002060`、补休 `92D050`、请假 `000000`、缺卡 `FF0000`。
4. 有打卡、全日班或白班时清除底色；多状态冲突不着色。
5. 保存 `_考勤标注.xlsx`，重新读取并逐格验证颜色和值。
6. 扫描公式错误及工作表结构变化。

### Task 11: 端到端编排和运行报告

**Files:**
- Create: `scripts/run_attendance.py`
- Create: `scripts/validate_outputs.py`
- Test: `tests/test_pipeline.py`

**Steps:**
1. 实现预检：凭据、模板、24h值班目录、数据预处理目录和年度工作日日历。
2. 缺少必要输入时立即停止，且不生成不完整输出。
3. 串联下载、解析、图片复核、归并、Word 和 Excel 输出。
4. 使用临时文件生成，验证成功后原子移动到最终文件名。
5. 输出成功摘要、统计数、缺失日期、未审批、低置信度、半天和冲突清单。
6. 运行端到端测试。

### Task 12: 真实8月资料验证

**Files:**
- Create: `evals/evals.json`
- Create: `attendance-statistics-workspace/iteration-1/`

**Steps:**
1. 在独立测试目录运行2026年8月资料，不覆盖现有文件。
2. 抽查签卡出勤、8月1日/15日/31日全日班、周末白班及已人工核对的休假记录。
3. 检查 Word 六项统计和 Excel 每日颜色。
4. 运行缺目录、未审批、半天、跨月和冲突测试。
5. 生成评审结果，邀请用户检查真实输出。

### Task 13: 定时任务与手动重跑

**Files:**
- Modify: `SKILL.md`
- Modify: `PROJECT_PROGRESS.md`

**Steps:**
1. 创建每月1日15:00（北京时间）的本地 Codex 定时任务。
2. 定时任务调用 Skill 统计上一个自然月。
3. 失败时只通知，不自动重试。
4. 在 Skill 中记录手动重跑入口和目标月份覆盖方式。
5. 查看定时任务配置并执行一次安全检查。

### Task 14: 完成验证与交付

**Files:**
- Modify: `PROJECT_PROGRESS.md`
- Modify: `PROJECT_RULES.md`（仅当实施产生新规则）

**Steps:**
1. 运行全部单元测试。
2. 扫描项目确认无明文凭据。
3. 验证示例输出可由 Word 和 Excel 正常打开。
4. 汇总测试结果、输出路径、已知限制和人工确认事项。
5. 请求用户提供版本名称后，仅提交本项目文件。

