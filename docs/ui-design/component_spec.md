# 智闻辨真：组件设计规范 (component_spec.md)

本规范定义了“智闻辨真”系统中基础组件的 HTML 布局结构、CSS 类命名规范（BEM 命名体系）以及交互反馈规则，确保在不引入完整框架依赖的前提下，制作出高精度、高一致性的前端原型。

---

## 1. 按钮组件 (Buttons)

系统使用统一的按钮基类 `.btn`。严禁混合使用不同大小、内边距和圆角的自定义类。

```html
<!-- 基础/主交互按钮 -->
<button class="btn btn--primary" type="button">立即检测</button>

<!-- 次级/取消/重置按钮 -->
<button class="btn btn--secondary" type="button">重置输入</button>

<!-- 危险动作按钮 -->
<button class="btn btn--danger" type="button">删除记录</button>

<!-- 带图标按钮 -->
<button class="btn btn--secondary btn--icon" type="button">
  <svg class="icon" ...></svg>
  <span>刷新数据</span>
</button>
```

### 1.1 按钮样式规格

* **尺寸 (Height)**：
  * 标准按钮高度为 `40px`，内边距 `0 16px`。
  * 小按钮（如表格内行操作、过滤器按钮）高度为 `32px`，内边距 `0 12px`，字号 `13px`。
* **圆角**：统一为 `var(--radius-md)` (6px)。
* **过渡动画 (Transition)**：
  ```css
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  ```
  包含背景色、边框色、阴影及微小缩放（悬浮时 `:hover` 略微上浮，点击时 `:active` 略微下沉 `1px`）。
* **无障碍 focus-visible**：当通过键盘 tab 键聚焦时，自动呈现 `var(--shadow-focus)`，禁止清除 `:focus` 轮廓线而不做任何替代。

---

## 2. 表单控件 (Forms)

表单布局采用 **“Label 置顶，Input 居中，提示/错误信息置底”** 的纵向卡片结构。

```html
<div class="form-group">
  <label class="form-label" for="news-title">新闻标题 <span class="form-label__required">*</span></label>
  <input class="form-input" id="news-title" type="text" placeholder="请输入需要检测的新闻标题..." required>
  <span class="form-helper">标题字数建议在 10-100 字之间，有利于召回精准证据。</span>
</div>

<!-- 错误状态示例 -->
<div class="form-group form-group--error">
  <label class="form-label" for="news-content">新闻正文</label>
  <textarea class="form-input form-input--textarea" id="news-content" placeholder="请输入正文..."></textarea>
  <span class="form-error-msg">新闻正文长度不能少于 50 字</span>
</div>
```

### 2.1 控件样式规格

* **表单框高度**：单行输入框、选择框高为 `40px`。文本域最小高度为 `200px`。
* **默认状态**：背景色为 `#ffffff`，边框为 `var(--color-border)`，文字颜色 `var(--color-text)`。
* **聚焦状态 (:focus)**：边框变为 `var(--color-primary)`，并附加 `var(--shadow-focus)` 的淡蓝色晕圈。
* **禁用状态 (:disabled)**：背景色变为 `var(--color-bg-subtle)`，文字颜色变为 `var(--color-text-muted)`，鼠标指针显示为 `not-allowed`。

---

## 3. 表格组件 (Data Tables)

表格专用于历史记录与管理员数据管理，要求高信息密度与极简横线划分。

```html
<div class="table-card">
  <div class="table-header">
    <h3 class="table-title">检测历史列表</h3>
    <span class="table-subtitle">共 128 条记录</span>
  </div>
  <table class="data-table">
    <thead>
      <tr>
        <th style="width: 40%">新闻标题</th>
        <th>检测时间</th>
        <th>可信度评分</th>
        <th>风险等级</th>
        <th class="text-right">操作</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td class="text-strong">华强北商家集体降价苹果手机促销</td>
        <td class="text-muted">2026-06-14 10:24</td>
        <td><strong class="score-text text-success">85 分</strong></td>
        <td><span class="risk-tag risk-tag--success">可信新闻</span></td>
        <td class="text-right">
          <a class="table-link" href="#">详情</a>
          <a class="table-link table-link--danger" href="#">删除</a>
        </td>
      </tr>
    </tbody>
  </table>
  <div class="table-pagination">
    <span>共 128 条记录，当前第 1 页</span>
    <div class="pagination-buttons">
      <button class="btn btn--small btn--secondary" disabled>上一页</button>
      <button class="btn btn--small btn--primary">1</button>
      <button class="btn btn--small btn--secondary">2</button>
      <button class="btn btn--small btn--secondary">3</button>
      <button class="btn btn--small btn--secondary">下一页</button>
    </div>
  </div>
</div>
```

### 3.1 表格样式规格

* **行高与对齐**：表头行高 `44px`，背景色 `var(--color-bg-subtle)`，粗体 `600`。普通数据行高 `52px`，只使用横向细分割线 `1px solid var(--color-border-soft)`，排除纵向竖线，符合现代网页排版。
* **Hover 反馈**：当鼠标划过每一行时，背景色微弱变为 `var(--color-primary-soft)` (透明度设为 0.3)，引导视线。

---

## 4. 内容卡片与面板 (Cards)

内容展示的底座，支持带标题页眉、无页眉和带语义色（风控等级）的卡片形态。

```html
<article class="card">
  <div class="card__header">
    <h2 class="card__title">三项指标分析</h2>
  </div>
  <div class="card__body">
    <!-- 内容 -->
  </div>
</article>

<!-- 风控卡片：高风险谣言色边装饰 -->
<article class="card card--danger">
  <div class="card__body">
    <h3 class="text-danger">高风险警告</h3>
    <p>该内容已被标注为谣言，请勿进行二次传播。</p>
  </div>
</article>
```

### 4.1 卡片样式规格

* **圆角与边框**：外轮廓统一为 `var(--radius-lg)` (10px)，默认带 `1px solid var(--color-border-soft)` 边框。
* **留白**：内填充 Padding 为 `var(--space-6)` (24px)。移动端自动折叠为 `var(--space-4)` (16px)。

---

## 5. ECharts 模拟图表规范 (Charts Dashboard)

在静态原型中，数据可视化卡片由 `.chart-panel` 包裹。

* **图表网格留白**：
  * 折线图/柱状图：ECharts `grid` 属性的 `top` 设为 `60px`，`bottom` 设为 `40px`，`left` 和 `right` 设为 `40px` (配合 `containLabel: true`)，避免标签被截断。
* **系统图表配色色板 (Theme Palette)**：
  ```javascript
  const chartColors = [
    '#0369a1', // 主色蓝
    '#16a34a', // 成功绿
    '#d97706', // 警示黄
    '#f97316', // 疑似橙
    '#dc2626', // 危险红
    '#0ea5e9'  // 检索青
  ];
  ```

---

## 6. 加载与空数据多状态 (Multi-States)

每一个展示组件均应支持在原型中手动触发（或预留）状态预览。

### 6.1 骨架屏加载 (Loading States)
* 使用细长的波浪形占位块，辅以闪烁呼吸动画，模拟数据从网络加载的效果：
  ```css
  .skeleton-line {
    height: 14px;
    background: linear-gradient(90deg, #f1f5f9 25%, #e2e8f0 50%, #f1f5f9 75%);
    background-size: 200% 100%;
    animation: skeleton-loading 1.5s infinite;
  }
  ```

### 6.2 统一空状态 (Empty States)
* 面板无数据时展示中立、友好的说明。包含一个精美的插画图标（由 SVG 线条图替代），说明语（灰字）以及一个核心行动引导按钮。

---

## 7. 弹窗与侧滑抽屉 (Modals & Drawers)

用于展示详情或后台管理审核操作，要求过渡动画平滑，背板附加模糊滤镜。

```html
<!-- 遮罩底板 -->
<div class="overlay overlay--visible">
  <!-- 右侧抽屉 -->
  <aside class="drawer drawer--visible">
    <header class="drawer__header">
      <h2 class="drawer__title">检测记录审核</h2>
      <button class="drawer__close-btn">&times;</button>
    </header>
    <div class="drawer__body">
      <!-- 审核表单 -->
    </div>
    <footer class="drawer__footer">
      <button class="btn btn--secondary">取消</button>
      <button class="btn btn--primary">提交审核</button>
    </footer>
  </aside>
</div>
```

### 7.1 模态样式规格

* **模糊背板**：
  ```css
  background-color: rgba(15, 23, 42, 0.4);
  backdrop-filter: blur(8px);
  ```
  遮罩层能够明显阻隔后方视线，提升专注力。
* **侧滑动画**：抽屉从屏幕右侧滑出，过渡参数 `transform 0.3s cubic-bezier(0.16, 1, 0.3, 1)`。
