<template>
  <div class="alert-rules-view">
    <div class="page-header">
      <h2>告警规则</h2>
      <el-button type="primary" :icon="Plus" @click="handleAdd">新建规则</el-button>
    </div>

    <el-card shadow="never">
      <el-table
        :data="rules"
        v-loading="loading"
        stripe
        style="width: 100%"
      >
        <el-table-column prop="name" label="规则名称" min-width="160" show-overflow-tooltip />
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.description || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="condition_type" label="类型" width="120">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">
              {{ getConditionLabel(row.condition_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="100" align="center">
          <template #default="{ row }">
            <el-tag
              :type="getPriorityTagType(row.priority)"
              size="small"
              effect="dark"
            >
              {{ getPriorityLabel(row.priority) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="通知渠道" width="200">
          <template #default="{ row }">
            <el-tag
              v-for="ch in (row.notify_channels || [])"
              :key="ch"
              size="small"
              effect="plain"
              style="margin-right: 4px; margin-bottom: 2px"
            >
              {{ getChannelLabel(ch) }}
            </el-tag>
            <span v-if="!row.notify_channels?.length">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="cooldown" label="冷却时间" width="100" align="center">
          <template #default="{ row }">
            {{ row.cooldown ? `${row.cooldown}s` : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="enabled" label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-switch
              :model-value="row.enabled"
              @change="(val: any) => handleToggleEnabled(row, val)"
            />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right" align="center">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click="handleEdit(row)">
              编辑
            </el-button>
            <el-popconfirm
              title="确定要删除该规则吗？"
              confirm-button-text="确定"
              cancel-button-text="取消"
              @confirm="handleDelete(row.id)"
            >
              <template #reference>
                <el-button size="small" type="danger" link>删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Create/Edit Dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEditing ? '编辑规则' : '新建规则'"
      width="720px"
      destroy-on-close
      @close="resetForm"
    >
      <el-form
        ref="formRef"
        :model="formData"
        :rules="formRules"
        label-width="100px"
      >
        <el-form-item label="规则名称" prop="name">
          <el-input v-model="formData.name" placeholder="请输入规则名称" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input
            v-model="formData.description"
            type="textarea"
            :rows="2"
            placeholder="请输入规则描述（可选）"
          />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="类型" prop="condition_type">
              <el-select v-model="formData.condition_type" placeholder="请选择类型" style="width: 100%">
                <el-option label="缺货告警" value="stockout" />
                <el-option label="超库存告警" value="overstock" />
                <el-option label="延迟告警" value="delay" />
                <el-option label="周转率告警" value="turnover" />
                <el-option label="自定义" value="custom" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="优先级" prop="priority">
              <el-select v-model="formData.priority" placeholder="请选择优先级" style="width: 100%">
                <el-option label="低" value="low" />
                <el-option label="中" value="medium" />
                <el-option label="高" value="high" />
                <el-option label="严重" value="critical" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <!-- Condition Builder -->
        <el-form-item label="触发条件">
          <div class="condition-builder">
            <div
              v-for="(cond, index) in formData.conditions"
              :key="index"
              class="condition-row"
            >
              <el-select
                v-model="cond.field"
                placeholder="字段"
                style="width: 140px"
              >
                <el-option label="库存数量" value="quantity" />
                <el-option label="可用数量" value="available_quantity" />
                <el-option label="库存天数" value="stock_days" />
                <el-option label="周转率" value="turnover_rate" />
                <el-option label="成本价" value="cost_price" />
                <el-option label="售价" value="selling_price" />
              </el-select>
              <el-select
                v-model="cond.operator"
                placeholder="运算符"
                style="width: 100px"
              >
                <el-option label="小于" value="lt" />
                <el-option label="小于等于" value="le" />
                <el-option label="等于" value="eq" />
                <el-option label="大于等于" value="ge" />
                <el-option label="大于" value="gt" />
                <el-option label="不等于" value="ne" />
              </el-select>
              <el-input
                v-model="cond.value"
                placeholder="值"
                style="width: 120px"
              />
              <el-button
                v-if="formData.conditions.length > 1"
                type="danger"
                :icon="Delete"
                circle
                size="small"
                @click="removeCondition(index)"
              />
            </div>

            <!-- Logic Toggle -->
            <div class="logic-toggle" v-if="formData.conditions.length > 1">
              <span>条件逻辑：</span>
              <el-radio-group v-model="formData.condition_logic" size="small">
                <el-radio-button value="and">AND (全部满足)</el-radio-button>
                <el-radio-button value="or">OR (任一满足)</el-radio-button>
              </el-radio-group>
            </div>

            <el-button
              type="primary"
              plain
              size="small"
              :icon="Plus"
              @click="addCondition"
              style="margin-top: 8px"
            >
              添加条件
            </el-button>
          </div>
        </el-form-item>

        <!-- Notification Channels -->
        <el-form-item label="通知渠道">
          <el-checkbox-group v-model="formData.notify_channels">
            <el-checkbox value="in_app" label="站内消息" />
            <el-checkbox value="email" label="邮件" />
            <el-checkbox value="sms" label="短信" />
            <el-checkbox value="webhook" label="Webhook" />
          </el-checkbox-group>
        </el-form-item>

        <el-form-item label="冷却时间(秒)" prop="cooldown">
          <el-input-number
            v-model="formData.cooldown"
            :min="0"
            :max="86400"
            :step="60"
            controls-position="right"
            style="width: 200px"
          />
          <span style="margin-left: 8px; color: #909399; font-size: 13px">
            同一规则在冷却期内不重复触发
          </span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleSubmit">
          {{ isEditing ? '保存修改' : '创建规则' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { Plus, Delete } from '@element-plus/icons-vue'
import {
  getAlertRules,
  createAlertRule,
  type AlertRule,
} from '@/api/alerts'
import request from '@/api/request'

// --- Types ---
interface Condition {
  field: string
  operator: string
  value: string
}

interface RuleFormData {
  name: string
  description: string
  condition_type: string
  priority: string
  conditions: Condition[]
  condition_logic: 'and' | 'or'
  notify_channels: string[]
  cooldown: number
  enabled: boolean
}

// --- State ---
const rules = ref<AlertRule[]>([])
const loading = ref(false)
const submitLoading = ref(false)

const dialogVisible = ref(false)
const isEditing = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance | null>(null)

const formData = reactive<RuleFormData>({
  name: '',
  description: '',
  condition_type: 'stockout',
  priority: 'medium',
  conditions: [{ field: 'quantity', operator: 'lt', value: '' }],
  condition_logic: 'and',
  notify_channels: ['in_app'],
  cooldown: 300,
  enabled: true,
})

const formRules: FormRules = {
  name: [{ required: true, message: '请输入规则名称', trigger: 'blur' }],
  condition_type: [{ required: true, message: '请选择类型', trigger: 'change' }],
  priority: [{ required: true, message: '请选择优先级', trigger: 'change' }],
}

// --- API ---
async function fetchRules() {
  loading.value = true
  try {
    const res = await getAlertRules({ page_size: 100 })
    rules.value = res.items || []
  } catch (err) {
    console.error('获取告警规则失败:', err)
    ElMessage.error('获取告警规则失败')
  } finally {
    loading.value = false
  }
}

function handleAdd() {
  isEditing.value = false
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

function handleEdit(row: AlertRule) {
  isEditing.value = true
  editingId.value = row.id
  Object.assign(formData, {
    name: row.name,
    description: row.description || '',
    condition_type: row.condition_type,
    priority: (row as any).priority || 'medium',
    conditions: (row as any).conditions || [{ field: 'quantity', operator: 'lt', value: String(row.threshold || '') }],
    condition_logic: (row as any).condition_logic || 'and',
    notify_channels: row.notify_channels || ['in_app'],
    cooldown: (row as any).cooldown || 300,
    enabled: row.enabled,
  })
  dialogVisible.value = true
}

async function handleSubmit() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return

    // Validate conditions
    const hasEmptyCondition = formData.conditions.some((c) => !c.value)
    if (hasEmptyCondition) {
      ElMessage.warning('请填写所有条件的值')
      return
    }

    submitLoading.value = true
    try {
      const data: any = {
        name: formData.name,
        description: formData.description || undefined,
        condition_type: formData.condition_type,
        priority: formData.priority,
        conditions: formData.conditions,
        condition_logic: formData.condition_logic,
        notify_channels: formData.notify_channels,
        cooldown: formData.cooldown,
        enabled: formData.enabled,
      }

      if (isEditing.value && editingId.value) {
        await request.put(`/alerts/rules/${editingId.value}`, data)
        ElMessage.success('规则更新成功')
      } else {
        await createAlertRule(data as any)
        ElMessage.success('规则创建成功')
      }
      dialogVisible.value = false
      fetchRules()
    } catch (err: any) {
      console.error('保存规则失败:', err)
      ElMessage.error(err?.response?.data?.message || '保存规则失败')
    } finally {
      submitLoading.value = false
    }
  })
}

async function handleDelete(id: number) {
  try {
    await request.delete(`/alerts/rules/${id}`)
    ElMessage.success('规则删除成功')
    fetchRules()
  } catch (err: any) {
    console.error('删除规则失败:', err)
    ElMessage.error(err?.response?.data?.message || '删除规则失败')
  }
}

async function handleToggleEnabled(row: AlertRule, val: boolean | string) {
  const enabled = val === true || val === 'true'
  try {
    await request.put(`/alerts/rules/${row.id}`, { enabled })
    row.enabled = enabled
    ElMessage.success(enabled ? '规则已启用' : '规则已停用')
  } catch (err: any) {
    console.error('切换规则状态失败:', err)
    ElMessage.error('切换规则状态失败')
  }
}

function addCondition() {
  formData.conditions.push({ field: 'quantity', operator: 'lt', value: '' })
}

function removeCondition(index: number) {
  formData.conditions.splice(index, 1)
}

function resetForm() {
  Object.assign(formData, {
    name: '',
    description: '',
    condition_type: 'stockout',
    priority: 'medium',
    conditions: [{ field: 'quantity', operator: 'lt', value: '' }],
    condition_logic: 'and',
    notify_channels: ['in_app'],
    cooldown: 300,
    enabled: true,
  })
  formRef.value?.resetFields()
}

// --- Helpers ---
function getConditionLabel(type: string): string {
  const map: Record<string, string> = {
    low_stock: '低库存',
    over_stock: '超库存',
    expiry: '过期预警',
    custom: '自定义',
    stockout: '缺货告警',
    overstock: '超库存告警',
    delay: '延迟告警',
    turnover: '周转率告警',
  }
  return map[type] || type
}

function getPriorityTagType(priority: string): 'success' | 'info' | 'warning' | 'danger' {
  const map: Record<string, 'success' | 'info' | 'warning' | 'danger'> = {
    low: 'success',
    medium: 'info',
    high: 'warning',
    critical: 'danger',
  }
  return map[priority] || 'info'
}

function getPriorityLabel(priority: string): string {
  const map: Record<string, string> = {
    low: '低',
    medium: '中',
    high: '高',
    critical: '严重',
  }
  return map[priority] || priority
}

function getChannelLabel(ch: string): string {
  const map: Record<string, string> = {
    in_app: '站内消息',
    email: '邮件',
    sms: '短信',
    webhook: 'Webhook',
  }
  return map[ch] || ch
}

// --- Lifecycle ---
onMounted(() => {
  fetchRules()
})
</script>

<style scoped lang="scss">
.alert-rules-view {
  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
  }

  .condition-builder {
    width: 100%;
    border: 1px solid #ebeef5;
    border-radius: 6px;
    padding: 12px;
    background: #fafafa;

    .condition-row {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 8px;
    }

    .logic-toggle {
      display: flex;
      align-items: center;
      gap: 8px;
      margin: 8px 0;
      padding: 8px 0;
      border-top: 1px dashed #dcdfe6;
      font-size: 13px;
      color: #606266;
    }
  }
}
</style>
