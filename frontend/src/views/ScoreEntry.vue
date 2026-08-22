<script setup>
/**
 * ScoreEntry.vue —— 成绩录入页
 * 双卡片布局：录入成绩 + 已录入成绩
 * 分数颜色：<60 红色、≥90 绿色
 */
import { ref, watch, onMounted, onActivated } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getStudents } from '@/api/students'
import { getSubjects } from '@/api/subjects'
import { useDataStore } from '../stores/dataStore'

const dataStore = useDataStore()
import { getScores, createScore, deleteScore, downloadExcel, importExcel } from '@/api/scores'

// ===== 录入成绩 =====
const selectedStudent = ref(null)
const selectedSubject = ref(null)
const inputScore = ref(null)
const submitting = ref(false)

// ===== 已录入成绩 =====
const viewStudent = ref(null)
const scoreList = ref([])
const scoreLoading = ref(false)

// ===== 下拉选项 =====
const studentOptions = ref([])
const subjectOptions = ref([])
const allSubjects = ref([])  // 完整科目列表，用于合并未录入科目

// ===== 数据加载 =====
async function loadStudents() {
  try {
    const res = await getStudents({ page: 1, page_size: 100 })
    studentOptions.value = res.items.map((s) => ({
      value: s.student_id,
      label: `${s.student_id}  ${s.name}`,
    }))
  } catch {
    ElMessage.error('加载学生列表失败')
  }
}

async function loadSubjects() {
  try {
    const list = await getSubjects()
    allSubjects.value = list
    subjectOptions.value = list.map((s) => ({ value: s.id, label: `${s.code} ${s.name}` }))
  } catch {
    ElMessage.error('加载科目列表失败')
  }
}

// 切换查看学生时刷新成绩，未录入的科目显示【未录入】
async function refreshScores(sid) {
  if (!sid) {
    scoreList.value = []
    return
  }
  scoreLoading.value = true
  try {
    const scores = await getScores(sid)
    const scoreMap = {}
    scores.forEach((s) => { scoreMap[s.subject_name] = s })

    // 合并：所有科目都显示，有成绩显示分数，没有显示"未录入"
    scoreList.value = allSubjects.value.map((sub) => {
      const existing = scoreMap[sub.name]
      if (existing) {
        return { ...existing, _unrecorded: false }
      }
      return {
        id: null,
        subject_name: sub.name,
        subject_id: sub.id,
        score: null,
        _unrecorded: true,
      }
    })
  } catch {
    ElMessage.error('加载成绩失败')
  } finally {
    scoreLoading.value = false
  }
}

watch(viewStudent, (sid) => refreshScores(sid))

// 刷新当前学生（录入/导入/删除后调用）
async function reloadCurrentStudent() {
  if (viewStudent.value) await refreshScores(viewStudent.value)
}

// ===== 录入成绩 =====
async function handleSubmit() {
  if (!selectedStudent.value || !selectedSubject.value || inputScore.value === null) {
    ElMessage.warning('请完整填写学生、科目和成绩')
    return
  }
  submitting.value = true
  try {
    await createScore({
      student_id: selectedStudent.value,
      subject_id: selectedSubject.value,
      score: inputScore.value,
    })
    ElMessage.success('录入成功')
    inputScore.value = null
    selectedSubject.value = null
    // 如果查看的就是该学生，自动刷新
    if (viewStudent.value === selectedStudent.value) {
      await reloadCurrentStudent()
    }
  } catch (err) {
    const msg = err?.response?.data?.detail || '录入失败'
    ElMessage.error(msg)
  } finally {
    submitting.value = false
  }
}

// ===== 删除成绩 =====
async function handleDelete(scoreId) {
  try {
    await ElMessageBox.confirm('确定删除这条成绩吗？', '确认删除', {
      type: 'warning',
      confirmButtonText: '确认删除',
      cancelButtonText: '取消',
    })
    await deleteScore(scoreId)
    ElMessage.success('删除成功')
    // 刷新当前学生的成绩
    await reloadCurrentStudent()
  } catch {
    // 取消
  }
}

// ===== 分数颜色 =====
function scoreColor(s) {
  if (s < 60) return '#F56C6C'   // 红色：不及格
  if (s >= 90) return '#67C23A'  // 绿色：优秀
  return '#606266'
}

// ===== Excel 操作 =====
async function downloadTemplate() {
  try {
    const blob = await downloadExcel('template')
    triggerDownload(blob, '成绩模板.xlsx')
    ElMessage.success('模板下载成功')
  } catch {
    ElMessage.error('模板下载失败')
  }
}

async function exportData() {
  try {
    const blob = await downloadExcel('full')
    triggerDownload(blob, '成绩数据.xlsx')
    ElMessage.success('数据导出成功')
  } catch {
    ElMessage.error('导出失败')
  }
}

async function handleImport(file) {
  try {
    const res = await importExcel(file)
    if (res.errors && res.errors.length > 0) {
      ElMessage.error(`导入失败：${res.errors.join('；')}`)
    } else {
      ElMessage.success(`导入完成：${res.success_count} 条`)
      // 如果正在查看某学生，刷新成绩
      await reloadCurrentStudent()
    }
  } catch (err) {
    const msg = err?.response?.data?.detail || '导入失败'
    ElMessage.error(msg)
  }
  return false  // 阻止 el-upload 自动上传
}

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

onMounted(() => {
  loadStudents()
  loadSubjects()
})
// AI 智能体修改数据后自动刷新
watch(() => dataStore.refreshKey, () => {
  loadStudents()
  loadSubjects()
  // 如果正在查看某个学生的成绩，刷新之
  if (viewStudent.value) refreshScores(viewStudent.value)
})

// 切换到成绩管理 Tab 时自动刷新
onActivated(() => {
  loadStudents()
  loadSubjects()
  if (viewStudent.value) refreshScores(viewStudent.value)
})
</script>

<template>
  <div>
    <h2 class="page-title">成绩管理</h2>

    <!-- 录入成绩卡片 -->
    <el-card style="margin-top:16px">
      <template #header><span style="font-weight:600">录入成绩</span></template>
      <div style="display:flex; gap:12px; align-items:flex-end; flex-wrap:wrap">
        <div>
          <div style="margin-bottom:4px; font-size:13px; color:#909399">选择学生</div>
          <el-select
            v-model="selectedStudent"
            placeholder="搜索学号或姓名"
            filterable
            style="width:200px"
          >
            <el-option
              v-for="s in studentOptions"
              :key="s.value"
              :label="s.label"
              :value="s.value"
            />
          </el-select>
        </div>
        <div>
          <div style="margin-bottom:4px; font-size:13px; color:#909399">选择科目</div>
          <el-select v-model="selectedSubject" placeholder="选择科目" style="width:180px">
            <el-option
              v-for="s in subjectOptions"
              :key="s.value"
              :label="s.label"
              :value="s.value"
            />
          </el-select>
        </div>
        <div>
          <div style="margin-bottom:4px; font-size:13px; color:#909399">成绩</div>
          <el-input-number
            v-model="inputScore"
            :min="0"
            :max="100"
            :precision="1"
            placeholder="0-100"
            style="width:120px"
          />
        </div>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">录 入</el-button>
      </div>
    </el-card>

    <!-- 已录入成绩卡片 -->
    <el-card style="margin-top:16px">
      <template #header>
        <div style="display:flex; justify-content:space-between; align-items:center">
          <span style="font-weight:600">已录入成绩</span>
          <el-select
            v-model="viewStudent"
            placeholder="选择学生查看成绩"
            clearable
            style="width:200px"
          >
            <el-option
              v-for="s in studentOptions"
              :key="s.value"
              :label="s.label"
              :value="s.value"
            />
          </el-select>
        </div>
      </template>

      <div v-if="!viewStudent" style="text-align:center; padding:40px; color:#909399">
        请先选择学生查看成绩
      </div>

      <el-table v-else :data="scoreList" v-loading="scoreLoading" style="width:100%" stripe>
        <el-table-column prop="subject_name" label="科目" min-width="150" />
        <el-table-column label="成绩" min-width="100">
          <template #default="{ row }">
            <span
              v-if="row._unrecorded"
              style="color:#C0C4CC; font-style:italic"
            >未录入</span>
            <span v-else :style="{ color: scoreColor(row.score), fontWeight: '600' }">
              {{ row.score }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="80">
          <template #default="{ row }">
            <el-button
              v-if="!row._unrecorded"
              type="danger" link size="small"
              @click="handleDelete(row.id)"
            >删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Excel 操作按钮 -->
    <div style="margin-top:16px; display:flex; gap:8px">
      <el-button @click="downloadTemplate">下载模板</el-button>
      <el-upload :show-file-list="false" :before-upload="handleImport" accept=".xlsx">
        <el-button type="primary">导入 Excel</el-button>
      </el-upload>
      <el-button type="success" @click="exportData">导出数据</el-button>
    </div>
  </div>
</template>
