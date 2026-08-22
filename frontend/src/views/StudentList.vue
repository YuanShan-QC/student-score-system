<script setup>
/**
 * StudentList.vue —— 学生管理页
 * 功能：搜索（防抖 300ms + Enter + 按钮）、分页、新增/编辑弹窗、删除确认
 */
import { ref, reactive, onMounted, onActivated, watch } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getStudents, createStudent, updateStudent, deleteStudent } from '@/api/students'
import { useDataStore } from '../stores/dataStore'

const dataStore = useDataStore()

// ===== 响应式数据 =====
const keyword = ref('')
const list = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref(null)

const pagination = reactive({ page: 1, page_size: 20, total: 0 })

const form = reactive({
  student_id: '',
  name: '',
  gender: '',
  age: null,
})

// ===== 表单校验规则 =====
const rules = {
  student_id: [{ required: true, message: '学号必填', trigger: 'blur' }],
  name: [{ required: true, message: '姓名必填', trigger: 'blur' }],
  gender: [{ required: true, message: '请选择性别', trigger: 'change' }],
  age: [
    { required: true, message: '年龄必填' },
    { type: 'number', min: 1, max: 150, message: '年龄 1-150', trigger: 'blur' },
  ],
}

// ===== 工具函数 =====
function formatDate(dateStr) {
  if (!dateStr) return '-'
  const d = new Date(dateStr)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

// 300ms 防抖自动搜索
let timer = null
watch(keyword, () => {
  clearTimeout(timer)
  timer = setTimeout(() => {
    pagination.page = 1
    fetchData()
  }, 300)
})

// ===== 数据加载 =====
async function fetchData() {
  loading.value = true
  try {
    const res = await getStudents({
      page: pagination.page,
      page_size: pagination.page_size,
      keyword: keyword.value || undefined,
    })
    list.value = res.items
    pagination.total = res.total
  } catch {
    ElMessage.error('加载学生列表失败')
  } finally {
    loading.value = false
  }
}

function onSearch() {
  pagination.page = 1
  fetchData()
}

function onPageChange(page) {
  pagination.page = page
  fetchData()
}

// ===== 表单操作 =====
function openAdd() {
  isEdit.value = false
  form.student_id = ''
  form.name = ''
  form.gender = ''
  form.age = null
  dialogVisible.value = true
}

function openEdit(row) {
  isEdit.value = true
  form.student_id = row.student_id
  form.name = row.name
  form.gender = row.gender
  form.age = row.age
  dialogVisible.value = true
}

async function handleSubmit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  try {
    if (isEdit.value) {
      await updateStudent(form.student_id, {
        name: form.name,
        gender: form.gender,
        age: form.age,
      })
      ElMessage.success('修改成功')
    } else {
      await createStudent({ ...form })
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
    await ElMessageBox.confirm(`确定删除学生「${row.name}」(学号:${row.student_id})吗？成绩也将级联删除。`, '确认删除', {
      type: 'warning',
      confirmButtonText: '确认删除',
      cancelButtonText: '取消',
    })
    await deleteStudent(row.student_id)
    ElMessage.success('删除成功')
    fetchData()
  } catch {
    // 用户取消
  }
}

onMounted(fetchData)
// AI 智能体修改数据后自动刷新
watch(() => dataStore.refreshKey, () => fetchData())
// 切换到学生管理 Tab 时自动刷新
onActivated(fetchData)
</script>

<template>
  <div>
    <h2 class="page-title">学生管理</h2>

    <div class="page-card">
      <!-- 搜索栏 -->
      <div class="toolbar">
        <div class="toolbar-left">
          <el-input
            v-model="keyword"
            placeholder="搜索姓名或学号"
            :prefix-icon="Search"
            style="width: 260px"
            clearable
            @keyup.enter="onSearch"
          />
          <el-button type="primary" @click="onSearch">搜索</el-button>
        </div>
        <el-button type="primary" @click="openAdd">新增学生</el-button>
      </div>

      <!-- 表格 -->
      <el-table :data="list" v-loading="loading" style="width:100%" stripe>
        <el-table-column prop="student_id" label="学号" min-width="120" />
        <el-table-column prop="name" label="姓名" min-width="100" />
        <el-table-column prop="gender" label="性别" min-width="80">
          <template #default="{ row }">
            <el-tag :type="row.gender === '男' ? '' : 'danger'" size="small" effect="light">
              {{ row.gender }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="age" label="年龄" min-width="80" />
        <el-table-column label="操作" min-width="140" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="openEdit(row)">编辑</el-button>
            <el-button type="danger" link size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="pagination.page"
          :page-size="pagination.page_size"
          :page-sizes="[10]"
          :total="pagination.total"
          background
          layout="total, prev, pager, next"
          @current-change="onPageChange"
        />
      </div>
    </div>

    <!-- 弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑学生' : '新增学生'"
      width="480px"
      @closed="formRef?.resetFields()"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="70px">
        <el-form-item label="学号" prop="student_id">
          <el-input v-model="form.student_id" :disabled="isEdit" placeholder="学号不可重复" />
        </el-form-item>
        <el-form-item label="姓名" prop="name">
          <el-input v-model="form.name" placeholder="请输入姓名" />
        </el-form-item>
        <el-form-item label="性别" prop="gender">
          <el-select v-model="form.gender" placeholder="请选择" style="width:100%">
            <el-option label="男" value="男" />
            <el-option label="女" value="女" />
          </el-select>
        </el-form-item>
        <el-form-item label="年龄" prop="age">
          <el-input-number v-model="form.age" :min="1" :max="150" style="width:100%" />
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
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.toolbar-left {
  display: flex;
  gap: 8px;
}
.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
