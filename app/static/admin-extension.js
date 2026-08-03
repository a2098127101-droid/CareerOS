(() => {
  "use strict";

  const qs = (selector, root = document) => root.querySelector(selector);
  const qsa = (selector, root = document) => [...root.querySelectorAll(selector)];
  const escapeHtml = (value = "") => String(value).replace(/[&<>"']/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[char]);
  const toast = (message, icon = "check") => CareerUI.toast(message, icon);
  const apiRequest = async (url, options = {}) => {
    const headers = options.body instanceof FormData ? {} : {"Content-Type": "application/json"};
    const legacy = localStorage.getItem("cc_admin_token") || "";
    if (legacy) headers["X-Admin-Token"] = legacy;
    const response = await fetch(url, {...options, credentials: "same-origin", headers: {...headers, ...(options.headers || {})}});
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = payload.detail;
      const message = typeof detail === "string" ? detail : detail?.message || detail?.code || "请求失败，请稍后重试。";
      throw new Error(window.CareerI18n?.t(message) || message);
    }
    return payload;
  };

  function installPanels() {
    const models = qs("#models");
    if (!models || qs("#templates")) return;
    models.insertAdjacentHTML("beforebegin", `
      <section class="admin-panel" id="templates">
        <div class="page-head"><div><div class="eyebrow">Template Registry</div><h1 style="margin-top:8px">模板配置</h1><p>工作流与成果模板保存到当前 Tenant；启用模板会形成真实版本记录。</p></div><button class="btn" id="refreshTemplates"><i data-lucide="refresh-cw"></i>刷新</button></div>
        <div class="permission-grid">
          <section><div class="section-head"><div><h2>工作流模板</h2><p>点击目录节点展开步骤，模板启用由后端保存。</p></div></div><div id="workflowTemplateTree" class="template-tree"><div class="skeleton skeleton-line wide"></div></div></section>
          <section class="card" style="padding:18px"><div class="section-head"><div><h3>创建工作流模板</h3></div></div>
            <div class="field"><label>Preset ID</label><input class="input" id="workflowPreset" value="career_development"></div>
            <div class="field" style="margin-top:10px"><label>模板名称</label><input class="input" id="workflowName"></div>
            <div class="field" style="margin-top:10px"><label>步骤 JSON</label><textarea class="textarea tall" id="workflowSteps">[{"id":"exploration","label":"自我探索"},{"id":"positioning","label":"职业定位"},{"id":"artifact","label":"成果提交"}]</textarea></div>
            <button class="btn primary" id="createWorkflowTemplate" style="margin-top:12px">创建模板</button>
          </section>
        </div>
        <section class="section"><div class="section-head"><div><h2>成果模板</h2><p>配置成果类型、渲染器与评审 Rubric。</p></div></div>
          <div id="artifactTemplateRows" class="config-list"></div>
          <div class="card" style="padding:18px;margin-top:16px"><div class="form-grid">
            <div class="field"><label>Kind</label><input class="input" id="artifactTemplateKind" value="career_report"></div>
            <div class="field"><label>Label</label><input class="input" id="artifactTemplateLabel" value="生涯发展报告"></div>
            <div class="field"><label>Renderer</label><input class="input" id="artifactTemplateRenderer" value="structured_text"></div>
            <div class="field"><label>Review Rubric</label><input class="input" id="artifactTemplateRubric" value="general_v1"></div>
          </div><button class="btn primary" id="createArtifactTemplate" style="margin-top:12px">创建模板</button></div>
        </section>
      </section>
      <section class="admin-panel" id="access">
        <div class="page-head"><div><div class="eyebrow">Tenant RBAC</div><h1 style="margin-top:8px">组织与权限</h1><p>所有角色与生命周期更新均由服务端 RBAC 校验，不依赖前端隐藏。</p></div><button class="btn" id="refreshAccess"><i data-lucide="refresh-cw"></i>刷新</button></div>
        <div id="permissionRows" class="config-list"><div class="skeleton-row"><div class="skeleton skeleton-line wide"></div></div></div>
      </section>`);
    CareerUI.refreshIcons();
    CareerI18n?.apply(qs("#templates"));
    CareerI18n?.apply(qs("#access"));
  }

  async function loadTemplates() {
    const [workflows, artifacts] = await Promise.all([
      apiRequest("/api/admin/templates/workflows"),
      apiRequest("/api/admin/templates/artifacts")
    ]);
    const workflowItems = workflows.templates || [];
    qs("#workflowTemplateTree").innerHTML = workflowItems.length ? workflowItems.map(item => `
      <div class="tree-node">
        <button class="tree-row" type="button" data-template-toggle>
          <i class="tree-chevron" data-lucide="chevron-right"></i><i data-lucide="folder"></i>
          <strong>${escapeHtml(item.name)}</strong><span>${escapeHtml(item.status || "draft")}</span>
        </button>
        <div class="tree-children"><div>
          ${(item.steps || []).map((step, index) => `<div class="tree-row depth-1"><i data-lucide="file-code-2"></i><strong>${index + 1}. ${escapeHtml(step.label || step.id)}</strong></div>`).join("")}
          <div class="tree-row depth-1"><button class="btn small primary" data-activate-workflow="${escapeHtml(item.template_id)}">启用</button></div>
        </div></div>
      </div>`).join("") : `<div class="empty compact-empty"><div><div class="empty-icon"><i data-lucide="layout-template"></i></div><p>当前 Tenant 尚无自定义工作流模板。</p></div></div>`;
    const artifactItems = artifacts.templates || [];
    qs("#artifactTemplateRows").innerHTML = artifactItems.length ? artifactItems.map(item => `
      <div class="config-item"><div class="config-top"><div><strong>${escapeHtml(item.label)}</strong><div class="meta">${escapeHtml(item.kind)} · ${escapeHtml(item.renderer)} · ${escapeHtml(item.review_rubric)}</div></div>
      <button class="btn small primary" data-activate-artifact-template="${escapeHtml(item.template_id)}">启用</button></div></div>`).join("") :
      `<div class="empty compact-empty"><div><p>当前 Tenant 尚无自定义成果模板。</p></div></div>`;
    qsa("[data-template-toggle]").forEach(button => button.onclick = () => button.closest(".tree-node").classList.toggle("open"));
    qsa("[data-activate-workflow]").forEach(button => button.onclick = () => activateTemplate("workflows", button.dataset.activateWorkflow, button));
    qsa("[data-activate-artifact-template]").forEach(button => button.onclick = () => activateTemplate("artifacts", button.dataset.activateArtifactTemplate, button));
    CareerUI.refreshIcons();
    CareerI18n?.apply(qs("#templates"));
  }

  async function activateTemplate(kind, id, button) {
    button.classList.add("button-busy");
    try {
      await apiRequest(`/api/admin/templates/${kind}/${encodeURIComponent(id)}/activate`, {method: "POST", body: "{}"});
      toast("模板已启用");
      await loadTemplates();
    } catch (error) {
      toast(error.message, "triangle-alert");
    } finally {
      button.classList.remove("button-busy");
    }
  }

  async function createWorkflow(button) {
    let steps;
    try { steps = JSON.parse(qs("#workflowSteps").value); }
    catch (_) { return toast("步骤 JSON 格式无效", "triangle-alert"); }
    if (!Array.isArray(steps) || !steps.length) return toast("至少需要一个工作流步骤", "triangle-alert");
    const name = qs("#workflowName").value.trim();
    if (!name) return toast("请输入模板名称", "triangle-alert");
    button.classList.add("button-busy");
    try {
      await apiRequest("/api/admin/templates/workflows", {method: "POST", body: JSON.stringify({
        preset_id: qs("#workflowPreset").value.trim(), name, steps
      })});
      qs("#workflowName").value = "";
      toast("工作流模板已创建");
      await loadTemplates();
    } catch (error) {
      toast(error.message, "triangle-alert");
    } finally { button.classList.remove("button-busy"); }
  }

  async function createArtifactTemplate(button) {
    const kind = qs("#artifactTemplateKind").value.trim();
    const label = qs("#artifactTemplateLabel").value.trim();
    if (!kind || !label) return toast("请填写 Kind 与 Label", "triangle-alert");
    button.classList.add("button-busy");
    try {
      await apiRequest("/api/admin/templates/artifacts", {method: "POST", body: JSON.stringify({
        kind, label, aliases: [], renderer: qs("#artifactTemplateRenderer").value.trim(),
        review_rubric: qs("#artifactTemplateRubric").value.trim(), presets: [qs("#workflowPreset").value.trim()], schema: {}
      })});
      toast("成果模板已创建");
      await loadTemplates();
    } catch (error) {
      toast(error.message, "triangle-alert");
    } finally { button.classList.remove("button-busy"); }
  }

  async function loadAccess() {
    const result = await apiRequest("/api/admin/users");
    const users = result.users || [];
    const canonicalRole = value => ({
      student: "participant", participant: "participant",
      teacher: "advisor", advisor: "advisor",
      school_admin: "organization_admin", organization_admin: "organization_admin",
      platform_admin: "super_admin", super_admin: "super_admin"
    })[value] || "participant";
    qs("#permissionRows").innerHTML = users.length ? users.map(user => {
      const selectedRole = canonicalRole(user.canonical_role || user.role);
      return `
      <div class="permission-row" data-user-id="${escapeHtml(user.user_id)}">
        <div><strong>${escapeHtml(user.display_name || user.email)}</strong><div class="meta">${escapeHtml(user.email)}</div></div>
        <select class="select permission-role" aria-label="角色">
          ${[
            ["participant", "User"], ["advisor", "Advisor"], ["organization_admin", "Organization Admin"], ["super_admin", "Platform Admin"]
          ].map(([value, label]) => `<option value="${value}" ${selectedRole === value ? "selected" : ""}>${label}</option>`).join("")}
        </select>
        <select class="select permission-status" aria-label="账户状态">
          ${["active", "disabled", "archived"].map(status => `<option value="${status}" ${user.status === status ? "selected" : ""}>${status}</option>`).join("")}
        </select>
        <button class="btn small primary" data-save-permission>保存</button>
      </div>`;
    }).join("") : `<div class="empty"><div><p>当前组织没有成员。</p></div></div>`;
    qsa("[data-save-permission]").forEach(button => {
      button.onclick = async () => {
        const row = button.closest("[data-user-id]");
        button.classList.add("button-busy");
        try {
          await apiRequest(`/api/admin/users/${encodeURIComponent(row.dataset.userId)}/role`, {
            method: "PATCH", body: JSON.stringify({role: qs(".permission-role", row).value})
          });
          await apiRequest(`/api/admin/users/${encodeURIComponent(row.dataset.userId)}/status`, {
            method: "PATCH", body: JSON.stringify({status: qs(".permission-status", row).value})
          });
          toast("权限分配已保存");
          await loadAccess();
        } catch (error) {
          toast(error.message, "triangle-alert");
        } finally { button.classList.remove("button-busy"); }
      };
    });
    CareerI18n?.apply(qs("#access"));
  }

  document.addEventListener("DOMContentLoaded", () => {
    installPanels();
    qs("#refreshTemplates").onclick = () => loadTemplates().catch(error => toast(error.message, "triangle-alert"));
    qs("#refreshAccess").onclick = () => loadAccess().catch(error => toast(error.message, "triangle-alert"));
    qs("#createWorkflowTemplate").onclick = event => createWorkflow(event.currentTarget);
    qs("#createArtifactTemplate").onclick = event => createArtifactTemplate(event.currentTarget);
    qs('[data-tab="templates"]').addEventListener("click", () => loadTemplates().catch(error => toast(error.message, "triangle-alert")));
    qs('[data-tab="access"]').addEventListener("click", () => loadAccess().catch(error => toast(error.message, "triangle-alert")));
    qs(".workspace-select")?.addEventListener("click", async () => {
      try {
        const me = await apiRequest("/api/auth/me");
        const user = me.user || {};
        CareerUI.modal({
          title: "系统工作区",
          description: "当前 Tenant 与权限由服务端身份决定",
          html: `<div class="workspace-list">
            <div class="workspace-row"><span>组织</span><strong>${escapeHtml(user.tenant_id || "—")}</strong></div>
            <div class="workspace-row"><span>角色</span><strong>${escapeHtml(user.canonical_role || user.role || "—")}</strong></div>
            <div class="workspace-row"><span>账户</span><strong>${escapeHtml(user.email || "—")}</strong></div>
          </div>`
        });
      } catch (error) { toast(error.message, "triangle-alert"); }
    });
    document.addEventListener("click", event => {
      const metric = event.target.closest(".metric");
      if (!metric || metric.closest(".career-modal")) return;
      const label = qs(".metric-label", metric)?.textContent || qs(".meta", metric)?.textContent || "系统指标";
      CareerUI.modal({
        title: label,
        description: "该指标来自当前 Tenant 的服务端数据",
        html: `<div class="workspace-row"><span>当前值</span><strong>${escapeHtml(qs(".metric-value", metric)?.textContent || "—")}</strong></div>`
      });
    });
  });
})();
