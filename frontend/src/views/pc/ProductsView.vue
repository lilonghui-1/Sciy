<template>
  <div class="products-view">
    <div class="page-header">
      <h2>产品管理</h2>
      <el-button type="primary" :icon="Plus" @click="handleAdd">添加产品</el-button>
    </div>

    <!-- Search & Filters -->
    <el-card shadow="never" class="filter-card">
      <el-row :gutter="16" align="middle">
        <el-col :span="8">
          <el-input
            v-model="searchText"
            placeholder="搜索产品名称或SKU..."
            clearable
            :prefix-icon="Search"
            @clear="fetchProducts"
            @keyup.enter="fetchProducts"
          />
        </el-col>
        <el-col :span="6">
          <el-select
            v-model="filterCategory"
            placeholder="选择分类"
            clearable
            @change="fetchProducts"
          >
            <el-option
              v-for="cat in categories"
              :key="cat"
              :label="cat"
              :value="cat"
            />
          </el-select>
        </el-col>
        <el-col :span="4">
          <el-select
            v-model="filterStatus"
            placeholder="状态"
            clearable
            @change="fetchProducts"
          >
            <el-option label="启用" value="active" />
            <el-option label="停用" value="inactive" />
          </el-select>
        </el-col>
        <el-col :span="6">
          <el-button type="primary" :icon="Search" @click="fetchProducts">搜索</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-col>
      </el-row>
    </el-card>

    <!-- Product Table -->
    <el-card shadow="never" style="margin-top: 16px">
      <el-table
        :data="products"
        v-loading="loading"
        stripe
        style="width: 100%"
        @sort-change="handleSortChange"
      >
        <el-table-column prop="sku" label="SKU" width="120" sortable="custom" />
        <el-table-column prop="name" label="名称" min-width="160" show-overflow-tooltip />
        <el-table-column prop="category" label="分类" width="120">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ row.category }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="unit" label="单位" width="80" align="center" />
        <el-table-column prop="cost_price" label="成本价" width="100" align="right">
          <template #default="{ row }">
            ¥{{ row.cost_price?.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="selling_price" label="售价" width="100" align="right">
          <template #default="{ row }">
            ¥{{ row.selling_price?.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="supplier" label="供应商" width="120" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.supplier || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="lead_time_days" label="提前期(天)" width="100" align="center">
          <template #default="{ row }">
            {{ row.lead_time_days ?? '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="safety_stock_days" label="安全库存(天)" width="110" align="center">
          <template #default="{ row }">
            {{ row.safety_stock_days ?? '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag
              :type="row.status === 'active' ? 'success' : 'info'"
              size="small"
            >
              {{ row.status === 'active' ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right" align="center">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click="handleEdit(row)">
              编辑
            </el-button>
            <el-popconfirm
              title="确定要删除该产品吗？"
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

      <!-- Pagination -->
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          background
          @size-change="fetchProducts"
          @current-change="fetchProducts"
        />
      </div>
    </el-card>

    <!-- Add/Edit Dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEditing ? '编辑产品' : '添加产品'"
      width="680px"
      destroy-on-close
      @close="resetForm"
    >
      <el-form
        ref="formRef"
        :model="formData"
        :rules="formRules"
        label-width="110px"
        label-position="right"
      >
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="SKU" prop="sku">
              <el-input v-model="formData.sku" placeholder="请输入SKU" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="产品名称" prop="name">
              <el-input v-model="formData.name" placeholder="请输入产品名称" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="分类" prop="category">
              <el-select v-model="formData.category" placeholder="请选择分类" filterable allow-create style="width: 100%">
                <el-option
                  v-for="cat in categories"
                  :key="cat"
                  :label="cat"
                  :value="cat"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="单位" prop="unit">
              <el-select v-model="formData.unit" placeholder="请选择单位" style="width: 100%">
                <el-option label="个" value="个" />
                <el-option label="件" value="件" />
                <el-option label="箱" value="箱" />
                <el-option label="包" value="包" />
                <el-option label="kg" value="kg" />
                <el-option label="g" value="g" />
                <el-option label="L" value="L" />
                <el-option label="mL" value="mL" />
                <el-option label="台" value="台" />
                <el-option label="套" value="套" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="成本价" prop="cost_price">
              <el-input-number
                v-model="formData.cost_price"
                :min="0"
                :precision="2"
                :step="0.1"
                controls-position="right"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="售价" prop="selling_price">
              <el-input-number
                v-model="formData.selling_price"
                :min="0"
                :precision="2"
                :step="0.1"
                controls-position="right"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="供应商" prop="supplier">
              <el-input v-model="formData.supplier" placeholder="请输入供应商" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="提前期(天)" prop="lead_time_days">
              <el-input-number
                v-model="formData.lead_time_days"
                :min="0"
                :max="365"
                controls-position="right"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="安全库存(天)" prop="safety_stock_days">
              <el-input-number
                v-model="formData.safety_stock_days"
                :min="0"
                :max="365"
                controls-position="right"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态" prop="status">
              <el-radio-group v-model="formData.status">
                <el-radio value="active">启用</el-radio>
                <el-radio value="inactive">停用</el-radio>
              </el-radio-group>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="最小库存" prop="min_stock">
              <el-input-number
                v-model="formData.min_stock"
                :min="0"
                controls-position="right"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="最大库存" prop="max_stock">
              <el-input-number
                v-model="formData.max_stock"
                :min="0"
                controls-position="right"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="描述" prop="description">
          <el-input
            v-model="formData.description"
            type="textarea"
            :rows="3"
            placeholder="请输入产品描述"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleSubmit">
          {{ isEditing ? '保存修改' : '创建产品' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import {
  getProducts,
  createProduct,
  updateProduct,
  deleteProduct,
  type Product,
  type CreateProductParams,
} from '@/api/products'

// --- State ---
const products = ref<Product[]>([])
const loading = ref(false)
const submitLoading = ref(false)
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const searchText = ref('')
const filterCategory = ref('')
const filterStatus = ref('')
const categories = ref<string[]>([])

// Dialog
const dialogVisible = ref(false)
const isEditing = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance | null>(null)

interface ProductFormData {
  sku: string
  name: string
  category: string
  unit: string
  cost_price: number
  selling_price: number
  supplier: string
  lead_time_days: number | undefined
  safety_stock_days: number | undefined
  status: string
  min_stock: number
  max_stock: number
  description: string
}

const formData = reactive<ProductFormData>({
  sku: '',
  name: '',
  category: '',
  unit: '',
  cost_price: 0,
  selling_price: 0,
  supplier: '',
  lead_time_days: undefined,
  safety_stock_days: undefined,
  status: 'active',
  min_stock: 0,
  max_stock: 0,
  description: '',
})

const formRules: FormRules = {
  sku: [{ required: true, message: '请输入SKU', trigger: 'blur' }],
  name: [{ required: true, message: '请输入产品名称', trigger: 'blur' }],
  category: [{ required: true, message: '请选择分类', trigger: 'change' }],
  unit: [{ required: true, message: '请选择单位', trigger: 'change' }],
  cost_price: [{ required: true, message: '请输入成本价', trigger: 'blur' }],
  selling_price: [{ required: true, message: '请输入售价', trigger: 'blur' }],
}

// --- API ---
async function fetchProducts() {
  loading.value = true
  try {
    const params: any = {
      page: currentPage.value,
      page_size: pageSize.value,
      search: searchText.value || undefined,
      category: filterCategory.value || undefined,
      sort_by: 'created_at',
      sort_order: 'desc',
    }
    if (filterStatus.value) {
      params.status = filterStatus.value
    }
    const res = await getProducts(params)
    products.value = res.items || []
    total.value = res.total || 0

    // Extract unique categories
    const catSet = new Set<string>()
    products.value.forEach((p) => {
      if (p.category) catSet.add(p.category)
    })
    categories.value = Array.from(catSet).sort()
  } catch (err) {
    console.error('获取产品列表失败:', err)
    ElMessage.error('获取产品列表失败')
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  searchText.value = ''
  filterCategory.value = ''
  filterStatus.value = ''
  currentPage.value = 1
  fetchProducts()
}

function handleSortChange({ prop, order }: any) {
  // Sorting handled server-side if needed
}

function handleAdd() {
  isEditing.value = false
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

function handleEdit(row: Product) {
  isEditing.value = true
  editingId.value = row.id
  Object.assign(formData, {
    sku: row.sku,
    name: row.name,
    category: row.category,
    unit: row.unit,
    cost_price: row.cost_price,
    selling_price: row.selling_price,
    supplier: (row as any).supplier || '',
    lead_time_days: (row as any).lead_time_days,
    safety_stock_days: (row as any).safety_stock_days,
    status: (row as any).status || 'active',
    min_stock: row.min_stock,
    max_stock: row.max_stock,
    description: row.description || '',
  })
  dialogVisible.value = true
}

async function handleSubmit() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    submitLoading.value = true
    try {
      const data: CreateProductParams = {
        sku: formData.sku,
        name: formData.name,
        category: formData.category,
        unit: formData.unit,
        cost_price: formData.cost_price,
        selling_price: formData.selling_price,
        min_stock: formData.min_stock,
        max_stock: formData.max_stock,
        description: formData.description || undefined,
      }

      // Include extra fields
      const extendedData: any = { ...data }
      if (formData.supplier) extendedData.supplier = formData.supplier
      if (formData.lead_time_days !== undefined) extendedData.lead_time_days = formData.lead_time_days
      if (formData.safety_stock_days !== undefined) extendedData.safety_stock_days = formData.safety_stock_days
      if (formData.status) extendedData.status = formData.status

      if (isEditing.value && editingId.value) {
        await updateProduct(editingId.value, extendedData)
        ElMessage.success('产品更新成功')
      } else {
        await createProduct(extendedData)
        ElMessage.success('产品创建成功')
      }
      dialogVisible.value = false
      fetchProducts()
    } catch (err: any) {
      console.error('保存产品失败:', err)
      ElMessage.error(err?.response?.data?.message || '保存产品失败')
    } finally {
      submitLoading.value = false
    }
  })
}

async function handleDelete(id: number) {
  try {
    await deleteProduct(id)
    ElMessage.success('产品删除成功')
    fetchProducts()
  } catch (err: any) {
    console.error('删除产品失败:', err)
    ElMessage.error(err?.response?.data?.message || '删除产品失败')
  }
}

function resetForm() {
  Object.assign(formData, {
    sku: '',
    name: '',
    category: '',
    unit: '',
    cost_price: 0,
    selling_price: 0,
    supplier: '',
    lead_time_days: undefined,
    safety_stock_days: undefined,
    status: 'active',
    min_stock: 0,
    max_stock: 0,
    description: '',
  })
  formRef.value?.resetFields()
}

// --- Lifecycle ---
onMounted(() => {
  fetchProducts()
})
</script>

<style scoped lang="scss">
.products-view {
  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
  }

  .filter-card {
    :deep(.el-card__body) {
      padding: 16px 20px;
    }
  }

  .pagination-wrapper {
    display: flex;
    justify-content: flex-end;
    margin-top: 16px;
    padding-top: 16px;
    border-top: 1px solid #ebeef5;
  }
}
</style>
