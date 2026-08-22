<script setup>
/**
 * SubjectList.vue —— 科目管理页
 * 功能：增删改科目，表格全宽 min-width
 */
import { ref, reactive, onMounted, onActivated, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getSubjects, createSubject, updateSubject, deleteSubject } from '@/api/subjects'
import { useDataStore } from '../stores/dataStore'

const dataStore = useDataStore()

// ===== 响应式数据 =====
const list = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref(null)

const form = reactive({ code: '', name: '' })

const rules = {
  code: [{ required: true, message: '科目编号必填', trigger: 'blur' }],
  name: [{ required: true, message: '科目名称必填', trigger: 'blur' }],
}

// ===== 数据加载 =====
function formatDate(dateStr) {
  if (!dateStr) return '-'
  const d = new Date(dateStr)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function fetchData() {
  loading.value = true
  try {
    list.value = await getSubjects()
  } catch {
    ElMessage.error('加载科目列表失败')
  } finally {
    loading.value = false
  }
}

// ===== 表单操作 =====
function openAdd() {
  isEdit.value = false
  form.code = ''
  form.name = ''
  dialogVisible.value = true
}

function openEdit(row) {
  isEdit.value = true
  form.code = row.code
  form.name = row.name
  dialogVisible.value = true
}

async function handleSubmit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  try {
    if (isEdit.value) {
      await updateSubject(form.code, { code: form.code, name: form.name })
      ElMessage.success('修改成功')
    } else {
      await createSubject({ code: form.code, name: form.name })
      ElMessage.success('添加成功')
    }
    dialogVisible.value = false
    fetchData()
  } catch (err) {
    const msg = err?.response?.data?.detail || '操作失败'
    ElMessage.error(msg)
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确定删除科目「${row.name}」(编号:${row.code})吗？`, '确认删除', {
      type: 'warning',
      confirmButtonText: '确认删除',
      cancelButtonText: '取消',
    })
    await deleteSubject(row.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch {
    // 用户取消
  }
}

onMounted(fetchData)
// AI 智能体修改数据后自动刷新
watch(() => dataStore.refreshKey, () => fetchData())
// 切换到科目管理 Tab 时自动刷新
onActivated(fetchData)
</script>

<template>
  <div>
    <h2 class="page-title">科目管理</h2>

    <div class="page-card">
      <!-- 工具栏 -->
      <div class="toolbar">
        <el-button type="primary" @click="openAdd">新增科目</el-button>
      </div>

      <!-- 表格 -->
      <el-table :data="list" v-loading="loading" style="width:100%" stripe>
        <el-table-column prop="id" label="ID" min-width="80" />
        <el-table-column prop="code" label="科目编号" min-width="120" />
        <el-table-column prop="name" label="科目名称" min-width="150" />
        <el-table-column label="操作" min-width="140" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="openEdit(row)">编辑</el-button>
            <el-button type="danger" link size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑科目' : '新增科目'"
      width="400px"
      @closed="formRef?.resetFields()"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="科目编号" prop="code">
          <el-input v-model="form.code" placeholder="如 MATH" />
        </el-form-item>
        <el-form-item label="科目名称" prop="name">
          <el-input v-model="form.name" placeholder="如 数学" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.toolbar {
  margin-bottom: 16px;
}
</style>
