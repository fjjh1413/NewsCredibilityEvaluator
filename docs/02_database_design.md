# 02 数据库设计文档

# 智闻辨真：数据库设计说明

> 本文档用于指导 MySQL 数据库表结构设计。  
> 后续使用 Codex 开发时，必须以本文档作为数据库字段、表名和关系设计依据。  
> 未经确认，不要随意修改表名、字段名和业务含义。

---

## 1. 数据库设计目标

本系统数据库主要用于保存以下数据：

1. 用户与角色信息；
2. 新闻知识库原始数据；
3. 新闻检测记录；
4. 检索证据匹配结果；
5. Prompt 模板；
6. 高风险新闻案例；
7. 检测报告；
8. 系统操作日志。

向量数据不直接存入 MySQL，而是存入 Chroma。  
MySQL 中只保存与 Chroma 对应的 `vector_id`，用于建立业务数据和向量数据之间的关联。

---

## 2. 数据库命名建议

数据库名称建议：

```sql
zhiyun_bianzhen
```

字符集建议：

```sql
utf8mb4
```

排序规则建议：

```sql
utf8mb4_unicode_ci
```

---

## 3. 表清单

系统建议包含以下核心表：

| 表名 | 中文名称 | 用途 |
|---|---|---|
| users | 用户表 | 保存普通用户和管理员信息 |
| knowledge_items | 新闻知识库表 | 保存新闻、辟谣样例和事实核查材料 |
| detection_records | 检测记录表 | 保存用户每次新闻检测结果 |
| evidence_matches | 证据匹配表 | 保存每次检测召回的相似证据 |
| prompt_templates | Prompt 模板表 | 保存可配置 Prompt 模板 |
| detection_records 高风险审核字段 | 高风险新闻审核数据 | 复用检测记录，保存审核与公开状态 |
| reports | 检测报告表 | 保存 HTML / PDF 报告路径 |
| system_logs | 系统日志表 | 保存用户和管理员操作日志 |

---

## 4. users 用户表

### 4.1 表作用

保存系统用户信息，包括普通用户和管理员。  
通过 `role` 字段区分用户身份。

### 4.2 字段设计

| 字段名 | 类型 | 是否必填 | 说明 |
|---|---|---|---|
| id | BIGINT | 是 | 主键，自增 |
| username | VARCHAR(50) | 是 | 用户名，唯一 |
| password_hash | VARCHAR(255) | 是 | 加密后的密码 |
| email | VARCHAR(100) | 否 | 邮箱 |
| role | VARCHAR(20) | 是 | 角色：user / admin |
| status | VARCHAR(20) | 是 | 状态：active / disabled |
| created_at | DATETIME | 是 | 创建时间 |
| updated_at | DATETIME | 是 | 更新时间 |

### 4.3 建表 SQL

```sql
CREATE TABLE users (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '用户ID',
    username VARCHAR(50) NOT NULL UNIQUE COMMENT '用户名',
    password_hash VARCHAR(255) NOT NULL COMMENT '加密后的密码',
    email VARCHAR(100) DEFAULT NULL COMMENT '邮箱',
    role VARCHAR(20) NOT NULL DEFAULT 'user' COMMENT '角色：user/admin',
    status VARCHAR(20) NOT NULL DEFAULT 'active' COMMENT '状态：active/disabled',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表';
```

---

## 5. knowledge_items 新闻知识库表

### 5.1 表作用

保存知识库中的新闻、谣言样例、辟谣说明和事实核查材料。  
原始文本保存在 MySQL，向量数据保存在 Chroma。  
`vector_id` 用于关联 Chroma 中的向量记录。

### 5.2 字段设计

| 字段名 | 类型 | 是否必填 | 说明 |
|---|---|---|---|
| id | BIGINT | 是 | 主键，自增 |
| title | VARCHAR(255) | 是 | 新闻标题 |
| content | TEXT | 是 | 新闻正文 |
| category | VARCHAR(50) | 否 | 新闻类别 |
| truth_label | VARCHAR(30) | 是 | 可信 / 存疑 / 谣言 |
| source_name | VARCHAR(100) | 否 | 来源名称 |
| source_url | VARCHAR(500) | 否 | 来源链接 |
| publish_time | DATETIME | 否 | 发布时间 |
| summary | TEXT | 否 | 新闻摘要 |
| keywords | VARCHAR(500) | 否 | 关键词，逗号分隔 |
| debunking_explanation | TEXT | 否 | 辟谣说明 |
| risk_level | VARCHAR(30) | 否 | 风险等级 |
| admin_note | TEXT | 否 | 管理员备注 |
| vector_id | VARCHAR(100) | 否 | Chroma 向量ID |
| created_at | DATETIME | 是 | 创建时间 |
| updated_at | DATETIME | 是 | 更新时间 |

### 5.3 建表 SQL

```sql
CREATE TABLE knowledge_items (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '知识库ID',
    title VARCHAR(255) NOT NULL COMMENT '新闻标题',
    content TEXT NOT NULL COMMENT '新闻正文',
    category VARCHAR(50) DEFAULT NULL COMMENT '新闻类别',
    truth_label VARCHAR(30) NOT NULL COMMENT '真实性标签：可信/存疑/谣言',
    source_name VARCHAR(100) DEFAULT NULL COMMENT '来源名称',
    source_url VARCHAR(500) DEFAULT NULL COMMENT '来源链接',
    publish_time DATETIME DEFAULT NULL COMMENT '发布时间',
    summary TEXT DEFAULT NULL COMMENT '新闻摘要',
    keywords VARCHAR(500) DEFAULT NULL COMMENT '关键词，逗号分隔',
    debunking_explanation TEXT DEFAULT NULL COMMENT '辟谣说明',
    risk_level VARCHAR(30) DEFAULT NULL COMMENT '风险等级',
    admin_note TEXT DEFAULT NULL COMMENT '管理员备注',
    vector_id VARCHAR(100) DEFAULT NULL COMMENT 'Chroma向量ID',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_category (category),
    INDEX idx_truth_label (truth_label),
    INDEX idx_risk_level (risk_level)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='新闻知识库表';
```

---

## 6. detection_records 检测记录表

### 6.1 表作用

保存用户每一次新闻检测的输入内容、评分结果、风险等级、判断理由和报告路径。

### 6.2 字段设计

| 字段名 | 类型 | 是否必填 | 说明 |
|---|---|---|---|
| id | BIGINT | 是 | 主键，自增 |
| user_id | BIGINT | 否 | 用户ID，游客可为空 |
| input_title | VARCHAR(255) | 是 | 输入新闻标题 |
| input_content | TEXT | 是 | 输入新闻正文 |
| category | VARCHAR(50) | 否 | 新闻类别 |
| keywords | VARCHAR(500) | 否 | 关键词 |
| final_score | DECIMAL(5,2) | 是 | 最终可信度评分 |
| evidence_score | DECIMAL(5,2) | 是 | 检索证据相关度评分 |
| llm_score | DECIMAL(5,2) | 是 | 大模型评分 |
| rule_score | DECIMAL(5,2) | 是 | 规则评分 |
| risk_level | VARCHAR(30) | 是 | 风险等级 |
| judgement_result | VARCHAR(100) | 是 | 判断结论 |
| reason | TEXT | 否 | 判断理由 |
| risk_points | TEXT | 否 | 风险点，JSON字符串 |
| suggestion | TEXT | 否 | 辟谣建议 |
| agent_steps | TEXT | 否 | Agent步骤，JSON字符串 |
| is_high_risk | TINYINT | 是 | 是否高风险 |
| review_status | VARCHAR(20) | 是 | pending / approved / rejected |
| is_public | TINYINT | 是 | 是否允许前台公开展示 |
| admin_remark | TEXT | 否 | 管理员内部备注 |
| reviewed_at | DATETIME | 否 | 审核时间 |
| reviewed_by | BIGINT | 否 | 审核管理员ID |
| report_url | VARCHAR(500) | 否 | 报告下载地址 |
| created_at | DATETIME | 是 | 创建时间 |

### 6.3 建表 SQL

```sql
CREATE TABLE detection_records (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '检测记录ID',
    user_id BIGINT DEFAULT NULL COMMENT '用户ID',
    input_title VARCHAR(255) NOT NULL COMMENT '输入新闻标题',
    input_content TEXT NOT NULL COMMENT '输入新闻正文',
    category VARCHAR(50) DEFAULT NULL COMMENT '新闻类别',
    keywords VARCHAR(500) DEFAULT NULL COMMENT '关键词',
    final_score DECIMAL(5,2) NOT NULL COMMENT '最终可信度评分',
    evidence_score DECIMAL(5,2) NOT NULL COMMENT '检索证据相关度评分',
    llm_score DECIMAL(5,2) NOT NULL COMMENT '大模型评分',
    rule_score DECIMAL(5,2) NOT NULL COMMENT '规则评分',
    risk_level VARCHAR(30) NOT NULL COMMENT '风险等级',
    judgement_result VARCHAR(100) NOT NULL COMMENT '判断结论',
    reason TEXT DEFAULT NULL COMMENT '判断理由',
    risk_points TEXT DEFAULT NULL COMMENT '风险点JSON',
    suggestion TEXT DEFAULT NULL COMMENT '辟谣建议',
    agent_steps TEXT DEFAULT NULL COMMENT 'Agent执行步骤JSON',
    is_high_risk TINYINT NOT NULL DEFAULT 0 COMMENT '是否高风险：0否，1是',
    review_status VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT '审核状态：pending/approved/rejected',
    is_public TINYINT NOT NULL DEFAULT 0 COMMENT '是否允许前台公开展示',
    admin_remark TEXT DEFAULT NULL COMMENT '管理员内部备注',
    reviewed_at DATETIME DEFAULT NULL COMMENT '审核时间',
    reviewed_by BIGINT DEFAULT NULL COMMENT '审核管理员ID',
    report_url VARCHAR(500) DEFAULT NULL COMMENT '报告下载地址',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_user_id (user_id),
    INDEX idx_risk_level (risk_level),
    INDEX idx_is_high_risk (is_high_risk),
    INDEX idx_detection_review_status (review_status),
    INDEX idx_detection_is_public (is_public),
    INDEX idx_detection_reviewed_by (reviewed_by),
    INDEX idx_created_at (created_at),
    CONSTRAINT fk_detection_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT fk_detection_reviewed_by FOREIGN KEY (reviewed_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='检测记录表';
```

---

## 7. evidence_matches 证据匹配表

### 7.1 表作用

保存每次检测召回的 Top-K 相似证据，用于结果页展示和报告生成。

### 7.2 字段设计

| 字段名 | 类型 | 是否必填 | 说明 |
|---|---|---|---|
| id | BIGINT | 是 | 主键，自增 |
| detection_id | BIGINT | 是 | 检测记录ID |
| knowledge_id | BIGINT | 否 | 知识库ID |
| title | VARCHAR(255) | 是 | 证据标题 |
| summary | TEXT | 否 | 证据摘要 |
| source_name | VARCHAR(100) | 否 | 来源名称 |
| similarity_score | DECIMAL(6,4) | 是 | 相似度评分 |
| rank_order | INT | 是 | 排名 |
| created_at | DATETIME | 是 | 创建时间 |

### 7.3 建表 SQL

```sql
CREATE TABLE evidence_matches (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '证据匹配ID',
    detection_id BIGINT NOT NULL COMMENT '检测记录ID',
    knowledge_id BIGINT DEFAULT NULL COMMENT '知识库ID',
    title VARCHAR(255) NOT NULL COMMENT '证据标题',
    summary TEXT DEFAULT NULL COMMENT '证据摘要',
    source_name VARCHAR(100) DEFAULT NULL COMMENT '来源名称',
    similarity_score DECIMAL(6,4) NOT NULL COMMENT '相似度评分',
    rank_order INT NOT NULL COMMENT '证据排名',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    UNIQUE INDEX uq_reports_detection_id (detection_id),
    INDEX idx_knowledge_id (knowledge_id),
    CONSTRAINT fk_evidence_detection FOREIGN KEY (detection_id) REFERENCES detection_records(id) ON DELETE CASCADE,
    CONSTRAINT fk_evidence_knowledge FOREIGN KEY (knowledge_id) REFERENCES knowledge_items(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='证据匹配表';
```

---

## 8. prompt_templates Prompt 模板表

### 8.1 表作用

保存不同类型的 Prompt 模板，支持管理员新增、编辑、删除、启用、停用和设为默认。

### 8.2 字段设计

| 字段名 | 类型 | 是否必填 | 说明 |
|---|---|---|---|
| id | BIGINT | 是 | 主键，自增 |
| name | VARCHAR(100) | 是 | 模板名称 |
| type | VARCHAR(50) | 是 | 模板类型 |
| content | TEXT | 是 | Prompt 内容 |
| is_default | TINYINT | 是 | 是否默认 |
| status | VARCHAR(20) | 是 | enabled / disabled |
| created_by | BIGINT | 否 | 创建人 |
| created_at | DATETIME | 是 | 创建时间 |
| updated_at | DATETIME | 是 | 更新时间 |

### 8.3 type 类型建议

```text
credibility_analysis：新闻可信度分析
keyword_extract：关键词提取
risk_analysis：风险点分析
debunking_suggestion：辟谣建议生成
report_generation：报告生成
```

### 8.4 建表 SQL

```sql
CREATE TABLE prompt_templates (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT 'Prompt模板ID',
    name VARCHAR(100) NOT NULL COMMENT '模板名称',
    type VARCHAR(50) NOT NULL COMMENT '模板类型',
    content TEXT NOT NULL COMMENT 'Prompt内容',
    is_default TINYINT NOT NULL DEFAULT 0 COMMENT '是否默认：0否，1是',
    status VARCHAR(20) NOT NULL DEFAULT 'enabled' COMMENT '状态：enabled/disabled',
    created_by BIGINT DEFAULT NULL COMMENT '创建人ID',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_type (type),
    INDEX idx_status (status),
    CONSTRAINT fk_prompt_user FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Prompt模板表';
```

---

## 9. 高风险新闻审核数据

### 9.1 表作用

当前实现复用 `detection_records` 作为高风险新闻唯一事实来源，不额外复制新闻正文、评分和证据。
检测保存时若 `final_score < 40` 或 `risk_level = '高风险谣言'`，自动设置 `is_high_risk=1`，并使用默认审核状态 `pending` 与默认公开状态 `is_public=0`。

### 9.2 字段设计

高风险审核字段直接位于 `detection_records`：

| 字段名 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| is_high_risk | TINYINT | 0 | 后端检测保存时自动标记 |
| review_status | VARCHAR(20) | pending | 待审核 / 审核通过 / 审核驳回 |
| is_public | TINYINT | 0 | 是否允许前台公开展示 |
| admin_remark | TEXT | NULL | 仅管理员可见的审核备注 |
| reviewed_at | DATETIME | NULL | 审核时间 |
| reviewed_by | BIGINT | NULL | 审核管理员ID |

现有数据库使用 Alembic 迁移升级：执行 `python -m app.db.migrate` 或在 `backend` 目录下执行 `alembic upgrade head`。高风险审核字段对应 Alembic 版本 `0002_add_high_risk_review_fields`，升级会将已有高风险记录统一设为待审核且不公开，避免历史数据未经审核直接展示。旧 SQL 文件仅保留在 `backend/migrations/legacy_sql/` 作为历史参考。

---

## 10. reports 检测报告表

### 10.1 表作用

保存检测报告记录，包括 HTML 报告和 PDF 报告路径。

### 10.2 字段设计

| 字段名 | 类型 | 是否必填 | 说明 |
|---|---|---|---|
| id | BIGINT | 是 | 主键，自增 |
| detection_id | BIGINT | 是 | 检测记录ID |
| user_id | BIGINT | 否 | 用户ID |
| report_title | VARCHAR(255) | 是 | 报告标题 |
| html_path | VARCHAR(500) | 否 | HTML 报告路径 |
| pdf_path | VARCHAR(500) | 否 | PDF 报告路径 |
| created_at | DATETIME | 是 | 创建时间 |

### 10.3 建表 SQL

```sql
CREATE TABLE reports (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '报告ID',
    detection_id BIGINT NOT NULL COMMENT '检测记录ID',
    user_id BIGINT DEFAULT NULL COMMENT '用户ID',
    report_title VARCHAR(255) NOT NULL COMMENT '报告标题',
    html_path VARCHAR(500) DEFAULT NULL COMMENT 'HTML报告路径',
    pdf_path VARCHAR(500) DEFAULT NULL COMMENT 'PDF报告路径',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_detection_id (detection_id),
    INDEX idx_user_id (user_id),
    CONSTRAINT fk_report_detection FOREIGN KEY (detection_id) REFERENCES detection_records(id) ON DELETE CASCADE,
    CONSTRAINT fk_report_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='检测报告表';
```

---

## 11. system_logs 系统日志表

### 11.1 表作用

保存系统操作日志，包括用户登录、新闻检测、知识库操作、Prompt 修改等。

### 11.2 字段设计

| 字段名 | 类型 | 是否必填 | 说明 |
|---|---|---|---|
| id | BIGINT | 是 | 主键，自增 |
| user_id | BIGINT | 否 | 操作用户ID |
| action | VARCHAR(100) | 是 | 操作动作 |
| module | VARCHAR(100) | 是 | 所属模块 |
| description | TEXT | 否 | 操作描述 |
| ip_address | VARCHAR(50) | 否 | IP 地址 |
| created_at | DATETIME | 是 | 创建时间 |

### 11.3 建表 SQL

```sql
CREATE TABLE system_logs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '日志ID',
    user_id BIGINT DEFAULT NULL COMMENT '用户ID',
    action VARCHAR(100) NOT NULL COMMENT '操作动作',
    module VARCHAR(100) NOT NULL COMMENT '所属模块',
    description TEXT DEFAULT NULL COMMENT '操作描述',
    ip_address VARCHAR(50) DEFAULT NULL COMMENT 'IP地址',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_user_id (user_id),
    INDEX idx_module (module),
    INDEX idx_created_at (created_at),
    CONSTRAINT fk_log_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='系统日志表';
```

---

## 12. 表关系说明

### 12.1 users 与 detection_records

一个用户可以有多条检测记录。

```text
users 1 —— N detection_records
```

### 12.2 detection_records 与 evidence_matches

一次检测可以召回多条证据。

```text
detection_records 1 —— N evidence_matches
```

### 12.3 knowledge_items 与 evidence_matches

一条知识库数据可以被多次召回。

```text
knowledge_items 1 —— N evidence_matches
```

### 12.4 detection_records 与 reports

一次检测通常对应一份报告。

```text
detection_records 1 —— 1 reports
```

### 12.5 detection_records 与高风险审核

高风险审核生命周期直接记录在 `detection_records`，不创建内容副本。公开接口只查询 `is_high_risk=1 AND review_status='approved' AND is_public=1`。

---

## 13. 枚举值约定

### 13.1 用户角色 role

```text
user：普通用户
admin：管理员
```

### 13.2 用户状态 status

```text
active：正常
disabled：禁用
```

### 13.3 知识库真实性标签 truth_label

```text
可信
存疑
谣言
```

### 13.4 风险等级 risk_level

```text
可信新闻
存疑信息
疑似谣言
高风险谣言
```

### 13.5 Prompt 状态 status

```text
enabled：启用
disabled：停用
```

### 13.6 高风险新闻审核状态 review_status

```text
pending：待审核
approved：已通过
rejected：已驳回
```

---

## 14. 初始化数据建议

### 14.1 初始管理员账号

建议初始化一个管理员账号：

```text
username：admin
password：由 seed 执行时的控制台输出或 DEMO_PASSWORD / ADMIN_DEMO_PASSWORD 环境变量确定
role：admin
```

实际开发时密码必须加密存储。

---

### 14.2 初始 Prompt 模板

建议初始化以下模板：

1. 新闻可信度分析 Prompt；
2. 关键词提取 Prompt；
3. 风险点分析 Prompt；
4. 辟谣建议生成 Prompt；
5. 报告生成 Prompt。

---

### 14.3 初始知识库数据

课程阶段建议先准备 30 条演示数据：

- 10 条可信新闻；
- 10 条存疑信息；
- 10 条谣言 / 辟谣样例。

后续扩展到 100 条左右。

---

## 15. Codex 开发要求

使用 Codex 生成数据库代码时，必须注意：

1. 表名和字段名以本文档为准；
2. 不要随意删减核心字段；
3. 使用 SQLAlchemy Model 时字段含义要与本文档一致；
4. 外键关系可以根据开发进度逐步实现；
5. 字段类型可以在合理范围内调整，但必须说明原因；
6. 检测记录中的 JSON 数据可以先用 TEXT 保存，后续再优化为 JSON 类型；
7. MySQL 保存原始数据，Chroma 保存向量数据，不要把向量直接写入 MySQL；
8. 每次修改数据库结构时，需要同步修改 Model、Schema 和迁移脚本。
