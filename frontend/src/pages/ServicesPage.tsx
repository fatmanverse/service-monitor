import { useEffect, useState } from 'react'
import { CheckCircle2, ChevronRight, PauseCircle, Pencil, Plus, Radar, Trash2, XCircle } from 'lucide-react'
import { api, errorMessage } from '../api'
import { AlertTargetPicker } from '../components/AlertTargetPicker'
import { RuleEditor } from '../features/rules/RuleEditor'
import { buildDefaultRule } from '../features/rules/healthRule'
import {
  blankProbe,
  blankServiceForm,
  buildServicePayload,
  serviceToForm,
  validateServiceForm,
  withProbes,
  type FormErrors,
  type ProbeDraft,
  type ServiceForm,
} from '../features/services/serviceForm'
import { formatDateTime } from '../lib/format'
import type { AlertConfig, Host, Probe, ResourceGroup, Service } from '../types'
import { StatusBadge, Tag } from '../ui/Badge'
import { Button } from '../ui/Button'
import { EmptyState, Notice, PageHeader, StatCard, StatGrid } from '../ui/Display'
import { CheckboxField, SelectField, TextareaField, TextField } from '../ui/Field'
import { Modal } from '../ui/Modal'
import { Toolbar, ToolbarCount, ToolbarSpacer } from '../ui/Toolbar'

const FORM_ID = 'service-form'

/** Sentinel filter value: services deliberately left without a resource group. */
const UNGROUPED_FILTER = 'ungrouped'

export function ServicesPage({
  isAdmin,
  onSelectService,
}: {
  isAdmin: boolean
  onSelectService: (serviceId: number) => void
}) {
  const [services, setServices] = useState<Service[]>([])
  const [hosts, setHosts] = useState<Host[]>([])
  const [groups, setGroups] = useState<ResourceGroup[]>([])
  const [alertConfigs, setAlertConfigs] = useState<AlertConfig[]>([])
  const [groupFilter, setGroupFilter] = useState('all')
  const [editing, setEditing] = useState<Service | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [form, setForm] = useState<ServiceForm>(blankServiceForm())
  const [errors, setErrors] = useState<FormErrors>({})
  const [message, setMessage] = useState('')

  async function load() {
    setServices(await api.services())
    if (!isAdmin) return
    const [hostResult, groupResult, alertResult] = await Promise.allSettled([
      api.hosts(),
      api.resourceGroups(),
      api.alerts(),
    ])
    if (hostResult.status === 'fulfilled') setHosts(hostResult.value)
    else setMessage(errorMessage(hostResult.reason))
    if (groupResult.status === 'fulfilled') setGroups(groupResult.value)
    else setMessage(errorMessage(groupResult.reason))
    if (alertResult.status === 'fulfilled') setAlertConfigs(alertResult.value)
  }

  useEffect(() => {
    load().catch((error) => setMessage(errorMessage(error)))
  }, [isAdmin])

  const filtered = groupFilter === 'all'
    ? services
    : groupFilter === UNGROUPED_FILTER
      ? services.filter((service) => service.resource_group_id == null)
      : services.filter((service) => service.resource_group_id === Number(groupFilter))
  const filterGroups = [...new Map(
    services.flatMap((service) => (
      service.resource_group_id == null
        ? []
        : [[service.resource_group_id, service.resource_group_name] as const]
    )),
  ).entries()]
  const ungroupedCount = services.filter((service) => service.resource_group_id == null).length

  function openCreate() {
    setEditing(null)
    setForm(blankServiceForm())
    setErrors({})
    setModalOpen(true)
  }

  function openEdit(service: Service) {
    setEditing(service)
    setForm(serviceToForm(service))
    setErrors({})
    setModalOpen(true)
  }

  function changeProbes(probes: ProbeDraft[]) {
    setForm((current) => withProbes(current, probes))
  }

  function updateProbe(index: number, patch: Partial<ProbeDraft>, syncRule = false) {
    setForm((current) => {
      const probes = current.probes.map((probe, itemIndex) => (
        itemIndex === index ? { ...probe, ...patch } : probe
      ))
      return syncRule ? withProbes(current, probes) : { ...current, probes }
    })
  }

  function toggleAlert(configId: number) {
    setForm((current) => ({
      ...current,
      alert_config_ids: current.alert_config_ids.includes(configId)
        ? current.alert_config_ids.filter((id) => id !== configId)
        : [...current.alert_config_ids, configId],
    }))
  }

  async function save(event: React.FormEvent) {
    event.preventDefault()
    setMessage('')
    const nextErrors = validateServiceForm(form)
    setErrors(nextErrors)
    if (Object.keys(nextErrors).length > 0) return

    try {
      const payload = buildServicePayload(form)
      if (editing) await api.updateService(editing.id, payload)
      else await api.createService(payload)
      setModalOpen(false)
      await load()
    } catch (error) {
      setMessage(errorMessage(error))
    }
  }

  async function remove(service: Service) {
    if (!confirm(`确认删除服务“${service.name}”？`)) return
    try {
      await api.deleteService(service.id)
      await load()
    } catch (error) {
      setMessage(errorMessage(error))
    }
  }

  return (
    <>
      <PageHeader
        title="服务监测"
        description="并发执行多个探活项，再按嵌套在线规则判断服务状态。"
        actions={isAdmin ? (
          <Button
            variant="primary"
            icon={<Plus size={16} />}
            onClick={openCreate}
            disabled={!hosts.length}
            title={!hosts.length ? '请先新增主机节点' : undefined}
          >
            新增服务
          </Button>
        ) : undefined}
      />
      {message && <Notice>{message}</Notice>}
      {isAdmin && !hosts.length && <Notice>新增服务前必须先创建主机节点。</Notice>}
      <StatGrid>
        <StatCard label="服务总数" value={services.length} icon={<Radar size={16} />} />
        <StatCard
          label="在线"
          value={services.filter((service) => service.status === 'online').length}
          tone="success"
          icon={<CheckCircle2 size={16} />}
        />
        <StatCard
          label="离线"
          value={services.filter((service) => service.status === 'offline').length}
          tone="danger"
          icon={<XCircle size={16} />}
        />
        <StatCard
          label="监控已停止"
          value={services.filter((service) => !service.enabled).length}
          tone="warning"
          icon={<PauseCircle size={16} />}
        />
      </StatGrid>
      <Toolbar>
        <div className="toolbar-filter">
          <SelectField
            label="资源组筛选"
            value={groupFilter}
            onChange={(event) => setGroupFilter(event.target.value)}
          >
            <option value="all">全部资源组</option>
            {filterGroups.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
            {ungroupedCount > 0 && <option value={UNGROUPED_FILTER}>未绑定资源组</option>}
          </SelectField>
        </div>
        <ToolbarSpacer />
        <ToolbarCount>{filtered.length} 个服务</ToolbarCount>
      </Toolbar>
      <section className="card-grid">
        {filtered.length === 0 ? (
          <div className="ui-card card-grid-full">
            <EmptyState
              icon={<Radar size={20} />}
              title="没有可见服务"
              description={isAdmin ? '请先创建资源组和主机，再配置服务。' : '管理员尚未向当前用户授权资源组。'}
            />
          </div>
        ) : filtered.map((service) => (
            <article
              className="service-card"
              key={service.id}
              role="link"
              tabIndex={0}
              onClick={() => onSelectService(service.id)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault()
                  onSelectService(service.id)
                }
              }}
            >
              <header className="service-card-head">
                <div className="service-card-icon"><Radar size={18} /></div>
                <div className="service-card-title">
                  <span>{service.resource_group_name ?? '未绑定资源组'} · {service.host_name}</span>
                  <h2>{service.name}</h2>
                </div>
                <StatusBadge status={service.status} />
              </header>
              <dl className="service-metrics">
                <div><dt>探活项</dt><dd>{service.probes.length}</dd></div>
                <div><dt>定时探活</dt><dd>{service.enabled ? `${service.check_interval}s` : '关闭'}</dd></div>
                <div><dt>响应</dt><dd>{service.last_response_ms == null ? '—' : `${service.last_response_ms}ms`}</dd></div>
                <div><dt>告警目标</dt><dd>{service.alert_configs.length}</dd></div>
              </dl>
              <div className="probe-chips">
                {service.probes.map((probe) => (
                  <Tag
                    key={probe.key}
                    tone={probe.last_success === true ? 'success' : probe.last_success === false ? 'danger' : undefined}
                  >
                    {probe.name}
                  </Tag>
                ))}
              </div>
              <p className="service-card-status" data-error={Boolean(service.last_error) || undefined}>
                {service.last_error || (service.last_checked_at ? `最近检查 ${formatDateTime(service.last_checked_at)}` : '等待首次探活')}
              </p>
              <footer className="service-card-footer" onClick={(event) => event.stopPropagation()}>
                <span className="service-card-link">查看详情 <ChevronRight size={15} /></span>
                {isAdmin && (
                  <>
                    <Button size="sm" variant="ghost" icon={<Pencil size={15} />} onClick={() => openEdit(service)}>
                      编辑
                    </Button>
                    <Button
                      size="icon"
                      variant="danger"
                      onClick={() => void remove(service)}
                      aria-label={`删除 ${service.name}`}
                      title="删除服务"
                    >
                      <Trash2 size={16} />
                    </Button>
                  </>
                )}
              </footer>
            </article>
        ))}
      </section>

      {modalOpen && (
        <Modal
          title={editing ? `编辑服务 · ${editing.name}` : '新增服务监测'}
          onClose={() => setModalOpen(false)}
          footer={(
            <>
              <Button variant="ghost" onClick={() => setModalOpen(false)}>取消</Button>
              <Button type="submit" form={FORM_ID} variant="primary">保存服务</Button>
            </>
          )}
        >
          <form id={FORM_ID} onSubmit={save}>
            <div className="form-grid">
              <SelectField
                label="所属节点"
                value={form.host_id}
                error={errors.host_id}
                onChange={(event) => setForm({ ...form, host_id: event.target.value })}
                required
              >
                <option value="">请选择</option>
                {hosts.map((host) => (
                  <option value={host.id} key={host.id}>
                    {host.name} · {host.execution_mode === 'agent' ? 'Agent' : 'SSH'}
                  </option>
                ))}
              </SelectField>
              <SelectField
                label="资源组"
                value={form.resource_group_id}
                error={errors.resource_group_id}
                hint="不绑定资源组的服务仅管理员可见，需在用户管理中单独授权。"
                onChange={(event) => setForm({ ...form, resource_group_id: event.target.value })}
              >
                <option value="">不绑定资源组</option>
                {groups.map((group) => <option value={group.id} key={group.id}>{group.name}</option>)}
              </SelectField>
              <TextField
                label="服务名称"
                value={form.name}
                error={errors.name}
                onChange={(event) => setForm({ ...form, name: event.target.value })}
                required
              />
              <TextField
                label="服务启动命令"
                value={form.start_command}
                error={errors.start_command}
                wide
                onChange={(event) => setForm({ ...form, start_command: event.target.value })}
              />
              <TextField
                label="启动用户"
                value={form.start_user}
                hint="留空则使用当前执行用户。"
                disabled={!form.start_command}
                pattern="[a-z_][a-z0-9_-]*"
                onChange={(event) => setForm({ ...form, start_user: event.target.value })}
              />
            </div>

            <section className="form-section">
              <header className="form-section-head">
                <div>
                  <h3>探活项</h3>
                  <p>增删或停用探活项时会同步在线规则，并保留仍然有效的组合结构。</p>
                </div>
                <Button
                  size="sm"
                  variant="secondary"
                  icon={<Plus size={15} />}
                  onClick={() => changeProbes([...form.probes, blankProbe(form.probes.length + 1)])}
                >
                  添加探活项
                </Button>
              </header>
              {errors.probes && <div className="form-error" role="alert">{errors.probes}</div>}
              <div className="probe-list">
                {form.probes.map((probe, index) => (
                  <ProbeEditor
                    key={probe.id ? `probe-${probe.id}` : `draft-${index}`}
                    probe={probe}
                    index={index}
                    errors={errors}
                    canRemove={form.probes.length > 1}
                    onChange={(patch, syncRule) => updateProbe(index, patch, syncRule)}
                    onRemove={() => changeProbes(form.probes.filter((_, itemIndex) => itemIndex !== index))}
                  />
                ))}
              </div>
            </section>

            <section className="form-section">
              <header className="form-section-head">
                <div>
                  <h3>在线规则</h3>
                  <p>表达式为真时服务在线；每个启用探活项必须且只能出现一次。</p>
                </div>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => setForm({ ...form, health_rule: buildDefaultRule(form.probes) })}
                >
                  重置规则
                </Button>
              </header>
              {errors.health_rule && <div className="form-error" role="alert">{errors.health_rule}</div>}
              <RuleEditor
                rule={form.health_rule}
                probes={form.probes}
                onChange={(health_rule) => setForm({ ...form, health_rule })}
              />
            </section>

            <section className="form-section">
              <div className="form-grid">
                <SelectField
                  label="定时规则"
                  value={form.enabled ? 'interval' : 'none'}
                  onChange={(event) => setForm({ ...form, enabled: event.target.value === 'interval' })}
                >
                  <option value="none">关闭</option>
                  <option value="interval">固定间隔</option>
                </SelectField>
                {form.enabled && (
                  <TextField
                    label="探活间隔（秒）"
                    type="number"
                    min="60"
                    max="86400"
                    value={form.check_interval}
                    error={errors.check_interval}
                    onChange={(event) => setForm({ ...form, check_interval: event.target.value })}
                    required
                  />
                )}
                <AlertTargetPicker
                  label="告警目标（可多选）"
                  configs={alertConfigs}
                  selectedIds={form.alert_config_ids}
                  onToggle={toggleAlert}
                />
                <CheckboxField
                  label="掉线自动拉起"
                  hint="服务判定离线后执行启动命令并立即复检。"
                  checked={form.auto_restart}
                  wide
                  onChange={(event) => setForm({ ...form, auto_restart: event.target.checked })}
                />
              </div>
            </section>
          </form>
        </Modal>
      )}
    </>
  )
}

function ProbeEditor({
  probe,
  index,
  errors,
  canRemove,
  onChange,
  onRemove,
}: {
  probe: ProbeDraft
  index: number
  errors: FormErrors
  canRemove: boolean
  onChange: (patch: Partial<ProbeDraft>, syncRule?: boolean) => void
  onRemove: () => void
}) {
  const error = (field: string) => errors[`probes.${index}.${field}`]

  return (
    <article className="probe-editor">
      <header className="probe-editor-head">
        <div className="probe-editor-head-text">
          <Radar size={16} />
          <strong>{probe.name || `探活项 ${index + 1}`}</strong>
        </div>
        <Button
          size="icon"
          variant="danger"
          disabled={!canRemove}
          onClick={onRemove}
          aria-label={`删除 ${probe.name || `探活项 ${index + 1}`}`}
          title={canRemove ? '删除探活项' : '至少保留一个探活项'}
        >
          <Trash2 size={16} />
        </Button>
      </header>
      <div className="probe-editor-body form-grid">
        <TextField
          label="规则标识"
          value={probe.key}
          error={error('key')}
          onChange={(event) => onChange({ key: event.target.value }, true)}
          required
        />
        <TextField
          label="显示名称"
          value={probe.name}
          error={error('name')}
          onChange={(event) => onChange({ name: event.target.value })}
          required
        />
        <SelectField
          label="类型"
          value={probe.probe_type}
          onChange={(event) => onChange({ probe_type: event.target.value as Probe['probe_type'] })}
        >
          <option value="process">进程 / systemd</option>
          <option value="get">GET</option>
          <option value="post">POST</option>
        </SelectField>
        <TextField
          label="超时（秒）"
          type="number"
          min="1"
          max="120"
          value={probe.timeout_seconds}
          error={error('timeout_seconds')}
          onChange={(event) => onChange({ timeout_seconds: Number(event.target.value) })}
        />
        {probe.probe_type === 'process' ? (
          <TextField
            label="进程匹配内容或 systemd 命令"
            value={probe.process_pattern || ''}
            error={error('process_pattern')}
            wide
            placeholder="进程关键字，或 systemctl status nginx"
            onChange={(event) => onChange({ process_pattern: event.target.value })}
            required
          />
        ) : (
          <>
            <TextField
              label="请求 URL"
              type="url"
              value={probe.url || ''}
              error={error('url')}
              wide
              onChange={(event) => onChange({ url: event.target.value })}
              required
            />
            <TextareaField
              label="Headers JSON"
              value={probe.headers}
              error={error('headers')}
              wide
              mono
              onChange={(event) => onChange({ headers: event.target.value })}
            />
            {probe.probe_type === 'post' && (
              <TextareaField
                label="Body JSON"
                value={probe.body}
                error={error('body')}
                wide
                mono
                onChange={(event) => onChange({ body: event.target.value })}
              />
            )}
            <SelectField
              label="认证"
              value={probe.auth_type}
              onChange={(event) => onChange({ auth_type: event.target.value as Probe['auth_type'] })}
            >
              <option value="none">无需认证</option>
              <option value="basic">Basic</option>
              <option value="bearer">Bearer</option>
            </SelectField>
            {probe.auth_type === 'basic' && (
              <TextField
                label="认证用户名"
                value={probe.auth_username || ''}
                error={error('auth_username')}
                onChange={(event) => onChange({ auth_username: event.target.value })}
                required
              />
            )}
            {probe.auth_type !== 'none' && (
              <TextField
                label="认证密钥"
                type="password"
                value={probe.auth_secret || ''}
                error={error('auth_secret')}
                hint={probe.id ? '留空保留原密钥。' : undefined}
                onChange={(event) => onChange({ auth_secret: event.target.value })}
                required={!probe.id}
              />
            )}
            <TextField
              label="期望状态码"
              type="number"
              min="100"
              max="599"
              value={probe.expected_status}
              error={error('expected_status')}
              onChange={(event) => onChange({ expected_status: Number(event.target.value) })}
            />
          </>
        )}
        <CheckboxField
          label="启用探活项"
          checked={probe.enabled}
          onChange={(event) => onChange({ enabled: event.target.checked }, true)}
        />
      </div>
    </article>
  )
}
