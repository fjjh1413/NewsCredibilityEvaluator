# 智闻辨真 UI/UX 重构设计方案 (ui_redesign_plan.md)

本方案旨在不改变任何业务功能、接口规范、数据结构、路由逻辑及功能按钮的前提下，对智闻辨真系统的用户端与管理员端进行深度的 UI/UX 视觉提升与规范化。

---

## 一、 前端目录结构概览

前端基于 Vue3 + Vite + Element Plus + ECharts 构建，目录树结构如下：

```
frontend/
├── index.html
├── package.json
├── vite.config.js
└── src/
    ├── main.js
    ├── App.vue
    ├── api/                     # 后端 API 请求模块
    ├── layouts/                 # 布局组件
    │   ├── UserLayout.vue       # 用户端整体外壳 (顶部导航)
    │   └── AdminLayout.vue      # 管理员端整体外壳 (侧边栏导航 + 面包屑)
    ├── router/                  # 路由配置
    │   └── index.js
    ├── stores/                  # 状态管理
    │   └── user.js
    ├── styles/                  # 样式文件
    │   ├── theme.css            # 设计系统 CSS 变量
    │   └── common.css           # 全局公用样式与组件覆写
    ├── utils/                   # 工具类
    ├── components/              # 公共及业务组件
    │   ├── admin/               # 管理端专用组件
    │   │   ├── AdminChartPanel.vue
    │   │   ├── AdminEndpointNotice.vue
    │   │   ├── AdminPageScaffold.vue
    │   │   └── AdminStatCard.vue
    │   ├── AgentSteps.vue       # 评估步骤条
    │   ├── EmptyState.vue       # 统一空状态
    │   ├── EvidenceList.vue     # 检索证据列表
    │   ├── LoadingState.vue     # 统一骨架屏加载
    │   ├── PageHeader.vue       # 页面统一页眉
    │   ├── ResultSection.vue    # 结果卡片容器
    │   ├── RiskLevelTag.vue     # 风险等级标签
    │   └── ScoreCard.vue        # 三项得分卡片
    └── views/                   # 视图页面
        ├── HomeView.vue         # 用户端首页
        ├── DetectView.vue       # 用户端新闻检测输入页
        ├── ResultView.vue       # 用户端检测结果详情页
        ├── HistoryView.vue      # 用户端历史记录页
        ├── HighRiskView.vue     # 用户端公开高风险新闻页
        ├── ProfileView.vue      # 用户端个人中心页
        ├── LoginView.vue        # 登录页
        ├── RegisterView.vue     # 注册页
        └── admin/               # 管理端视图页面
            ├── AdminDashboardView.vue    # 后台首页
            ├── AdminUsersView.vue        # 用户管理页
            ├── AdminDetectionsView.vue   # 检测记录管理页
            ├── AdminKnowledgeView.vue    # 知识库管理页
            ├── AdminPromptsView.vue      # Prompt 模板管理页
            ├── AdminHighRiskView.vue     # 高风险新闻管理页
            ├── AdminStatisticsView.vue    # 数据统计分析页
            ├── AdminReportsView.vue      # PDF 报告管理页
            └── AdminLogsView.vue         # 系统日志审计页
```

---

## 二、 页面和组件清单

### 1. 页面 (Views) - 共 17 个
* **用户端页面 (8个):**
  * `HomeView.vue` (门户首页)
  * `LoginView.vue` (登录)
  * `RegisterView.vue` (注册)
  * `DetectView.vue` (检测输入)
  * `ResultView.vue` (结果呈现与报告下载)
  * `HistoryView.vue` (个人历史记录)
  * `HighRiskView.vue` (公开的谣言高风险榜单)
  * `ProfileView.vue` (个人中心)
* **管理员端页面 (9个):**
  * `admin/AdminDashboardView.vue` (后台首页)
  * `admin/AdminUsersView.vue` (账户与角色管理)
  * `admin/AdminDetectionsView.vue` (检测记录管理)
  * `admin/AdminKnowledgeView.vue` (RAG 知识库与向量同步)
  * `admin/AdminPromptsView.vue` (Prompt 模板生命周期管理)
  * `admin/AdminHighRiskView.vue` (高风险审核队列与公开配置)
  * `admin/AdminStatisticsView.vue` (多维度数据看板)
  * `admin/AdminReportsView.vue` (PDF 文件状态与管理)
  * `admin/AdminLogsView.vue` (系统审计日志)

### 2. 布局 (Layouts) - 共 2 个
* `UserLayout.vue` (用户端两栏式流式布局，顶部吸顶导航)
* `AdminLayout.vue` (管理端左侧固定侧边栏 + 右侧顶栏与主体网格布局)

### 3. 公共组件 (Components) - 共 12 个
* **通用组件 (8个):**
  * `PageHeader.vue`: 带有渐变背板的现代页头，提供操作插槽。
  * `RiskLevelTag.vue`: 统一展示四种风险等级（可信、存疑、疑似谣言、高风险谣言）。
  * `ScoreCard.vue`: 指标得分展示卡片，支持 primary/warning/danger/neutral 等多种色调。
  * `AgentSteps.vue`: 展示 RAG+LLM 分析的阶段步骤状态。
  * `ResultSection.vue`: 结果分块的容器卡片。
  * `EvidenceList.vue`: 召回证据 Top 10 的列表卡片及相似度进度条。
  * `EmptyState.vue`: 自定义插槽的统一空数据占位。
  * `LoadingState.vue`: 统一的行级骨架屏加载状态。
* **后台专属组件 (4个):**
  * `AdminStatCard.vue`: 后台统计卡片，支持骨架屏集成。
  * `AdminChartPanel.vue`: 抽象 ECharts 加载、无数据占位和自适应宽度的容器组件。
  * `AdminEndpointNotice.vue`: 接口未就绪的警示性信息组件。
  * `AdminPageScaffold.vue`: 空闲或二级页面的标准页架。

---

## 三、 当前 UI/UX 问题清单

### 1. 视觉层级与排版不规范
* **字体大小混杂**: 在 `common.css` 和 scoped 样式中，存在多处硬编码的字号（如 17px, 34px, 44px），偏离了 `theme.css` 中定义的以 2-4px 递增的字号规范。
* **色彩一致性欠佳**: 部分组件直接使用硬编码的 Hex 色值（如 `#ffffff`, `#E0F2FE`）和 rgba 灰度，而没有引用 `--color-text-muted` 或 `--color-border` 等系统 Token。
* **卡片式过度分块**: `ResultView.vue` 和 `ProfileView.vue` 中卡片过多、间距设置不一。有的 padded 为 24px，有的为 20px，导致页面碎裂感严重，信息流缺乏自然引导。

### 2. 用户端与管理端的组件风格未统一
* **按钮混用**: 用户端使用原生自定义按钮 `.button--primary`，而管理端或表单内部分又混合使用 Element Plus 的 `<el-button>`。虽然覆盖了部分 Element 变量，但按钮圆角和阴影、hover 缩放时长在视觉上仍能看出两套风格。
* **表单筛选区差异**:
  * 用户端（如 `HistoryView.vue`）使用 `el-form` 配合 input。
  * 管理员端（如 `AdminUsersView.vue`、`AdminHighRiskView.vue`）则混合使用了原生的 `<label class="filter-field">` 以及 Element 的 `el-select`。原生 Input 与 Element Plus 的样式有明显色差和尺寸失调（原生高度与 Element 40px 高度不一致）。
* **弹窗与侧滑面板不一致**: 后台管理操作（如用户详情、审核备注）采用纯手工定制的 `.user-panel-overlay`（侧边滑动抽屉样式），而非 Element Plus 统一的 Drawer 或 Dialog，缺乏统一的转场动效与遮罩层模糊度规范。

### 3. CSS 冗余与可维护性差
* **重复的表格和筛选样式**: 9 个后台页面几乎都在 scoped styles 中复制了 `.filter-panel` / `.admin-users__filter` 及其内部元素的样式，以及表格下方的分页 `.pagination` 排版。一旦重构间距或边框，需修改十余个文件。
* **过度使用 scoped 对 Element 组件进行穿透修改**: 充斥着大量的 `:deep(.el-table)` 样式覆写，且实现方式不一，导致表格的 hover 行背景色、表头加粗等全局视觉在不同子页面出现微调偏差。

### 4. 响应式与设备适配边缘缺陷
* **1366×768（小屏笔记本）**: 
  * 管理后台侧边栏（264px）在 1366 宽下会过度挤压右侧内容。由于表格字段较多（如系统日志的描述与 IP），未设置合理的 `min-width` 会导致内容挤压并产生多层折行。
* **移动端（竖屏）**:
  * 某些弹窗/抽屉（`.user-panel`）在移动端没有自适应为 100% 宽度，或底部操作按钮被安全区域遮挡。
  * 首页核心功能板块 `home-workflow` 的五步流程在小屏下横向排列虽有折行，但间距错位严重。

---

## 四、 推荐的整体视觉方向

为建立统一、可信任的“企业级安全风控与 AI 决策”感官，设计系统应向 **Enterprise Minimalism & Trust** 靠拢：
1. **主色调（可信）**: 以深海蓝（`#0C4A6E`）和科技蓝（`#0369A1`）为主基调，以大面积精致的冷白（`#F5F9FC`）做页面背景。
2. **警示色（风控）**: 精确匹配并固化绿（可信）、黄（存疑）、橙（疑似谣言）、红（高风险谣言）的饱和度。
3. **极简圆角与精致投影**:
   * 大卡片统一收束为 `var(--radius-lg)`（10px），表单、按钮与标签为 `var(--radius-sm)`（6px）。
   * 采用弥散且超低浓度的软投影：`box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04)`。
4. **统一布局基类**: 建立一组全局通用版面类（例如：`.evaluator-filter-bar`, `.evaluator-table-card`, `.evaluator-pagination-wrap`），收拢冗余 CSS。

---

## 五、 分阶段改造顺序

本次改造遵循 **“先全局设计系统，后通用布局，再分端推进，最后兼容优化”** 的顺序，具体分为 5 个阶段：

```
【阶段 1】全局设计系统与基础重构 (Theme & Common CSS)
     │
【阶段 2】用户端重点页面重构 (Detect & Result)
     │
【阶段 3】管理员端公共布局与卡片标准化 (Admin Shell & Scaffold)
     │
【阶段 4】管理员端业务管理列表重构 (Table & Filter Scoped Style Sync)
     │
【阶段 5】响应式调优、弱网/错误状态覆盖与最终回归测试
```

---

## 六、 每个阶段预计修改的文件

在不改变任何数据链路和 API 前提下，预计修改以下文件：

### 阶段 1：全局设计系统规范与基础重构
* **目的**: 规范色彩变量、排版、阴影，建立全局通用原子类，覆写 Element Plus 全局样式。
* **涉及文件**:
  * `frontend/src/styles/theme.css` (调整变量层级与 Element Plus 变量映射)
  * `frontend/src/styles/common.css` (封装通用布局类如 `.evaluator-filter`、`.evaluator-pagination`)
  * `frontend/src/App.vue` (引入全局字体与基础滚动条平滑处理)

### 阶段 2：用户端核心流程（新闻检测与结果）重构
* **目的**: 提升输入体验与评估报告的信任度，统一三项得分卡片和证据列表的自适应。
* **涉及文件**:
  * `frontend/src/views/DetectView.vue` (表单排版优化，提示层级对齐)
  * `frontend/src/views/ResultView.vue` (重排版 final_score 主卡片，去除碎片卡片，强化 PDF 操作的 UI 反馈)
  * `frontend/src/components/ScoreCard.vue` (统一圆角与字体规范)
  * `frontend/src/components/EvidenceList.vue` (美化相似度对比进度条)
  * `frontend/src/views/HomeView.vue` (优化流程卡片响应式)

### 阶段 3：管理端主布局与状态组件重构
* **目的**: 规范后台侧边栏，将 custom drawer/modal 统一以组件或通用 CSS 类管理。
* **涉及文件**:
  * `frontend/src/layouts/AdminLayout.vue` (侧边栏与面包屑的留白、投影优化，适配 1366 屏幕宽度)
  * `frontend/src/components/admin/AdminChartPanel.vue` (优化 ECharts 网格间距与标题字号)
  * `frontend/src/components/admin/AdminStatCard.vue` (统一边框与阴影)

### 阶段 4：管理员端表格与过滤条件重构
* **目的**: 清理 9 个后台管理页面中高度重复的 filter-panel 样式，收纳到全局通用样式中。
* **涉及文件**:
  * `frontend/src/views/admin/AdminUsersView.vue`
  * `frontend/src/views/admin/AdminDetectionsView.vue`
  * `frontend/src/views/admin/AdminKnowledgeView.vue`
  * `frontend/src/views/admin/AdminPromptsView.vue`
  * `frontend/src/views/admin/AdminHighRiskView.vue`
  * `frontend/src/views/admin/AdminReportsView.vue`
  * `frontend/src/views/admin/AdminLogsView.vue`
  * `frontend/src/views/admin/AdminStatisticsView.vue`

### 阶段 5：跨端响应式与状态优化
* **目的**: 解决小屏笔记本、iPad、移动端适配体验，补充弱网加载与离线错误状态。
* **涉及文件**:
  * `frontend/src/components/EmptyState.vue`
  * `frontend/src/components/LoadingState.vue`
  * `frontend/src/views/ProfileView.vue` (个人中心及快捷入口卡片排版微调)
  * `frontend/src/views/HistoryView.vue` (历史记录表头响应式折行优化)

---

## 七、 UI 改造风险与回归测试点

由于不涉及业务重构，测试应侧重于**排版兼容性与响应式回归**：

### 1. 样式穿透引起的全局污染风险
* **风险点**: 覆写 Element Plus 全局样式时可能导致第三方弹窗或第三方控件出现隐式位移。
* **回归点**: 检查 `ElMessageBox.confirm`（例如：退出登录确认框）、`ElNotification`、`ElLoading` 以及 `v-loading` 遮罩的圆角和背景模糊是否表现正常。

### 2. 宽度与内容溢出风险
* **风险点**: 在 1366×768 及更窄屏下，表格列由于文字较长（如 IP 地址、邮箱、备注）可能导致文字溢出、换行重叠，或者出现纵向与横向双向滚动条。
* **回归点**: 在 Chrome DevTools 中切换 `1366x768` 物理分辨率，对系统日志页、检测记录管理页的表格列宽进行宽度拉伸测试。

### 3. ECharts 图表尺寸未按比例重绘风险
* **风险点**: 在侧边栏折叠、窗口尺寸改变（尤其是 1024px 以下切换）时，ECharts 未能正确调用 `resize()` 导致画布被截断或超出。
* **回归点**: 频繁缩放浏览器窗口，验证后台首页及统计页面的 6 个图表是否能够平滑自适应。

### 4. 路由与未登录拦截下的布局闪烁风险
* **风险点**: 从游客端切入管理员端，由于重构了外层 shell 的 background, 可能在拦截跳转至 `/login` 的那一瞬间出现白屏或背景突变。
* **回归点**: 模拟游客点击 /admin 下受保护路由，检查页面重定向瞬间的 UI 过渡。
