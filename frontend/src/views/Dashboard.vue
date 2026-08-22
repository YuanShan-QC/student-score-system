<script setup>
/**
 * Dashboard.vue —— 数据看板首页
 * 顶部 4 个统计卡片 + 两张 ECharts 图表（各科目平均分柱状图、分数段分布饼图）
 */
import { ref, onMounted, onActivated, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { getStats } from '@/api/stats'
import { useDataStore } from '../stores/dataStore'

const dataStore = useDataStore()

// ===== 统计数据 =====
const stats = ref({
  student_count: 0,
  subject_count: 0,
  score_count: 0,
  avg_score: 0,
  max_score: 0,
  min_score: 0,
  pass_rate: 0,
  subject_stats: [],
  distribution: [],
})

// 图表 DOM 引用
const barChartRef = ref(null)
const pieChartRef = ref(null)
let barChart = null
let pieChart = null

// ===== 加载数据 =====
async function loadStats() {
  try {
    stats.value = await getStats()
    await nextTick()
    renderCharts()
  } catch {
    ElMessage.error('加载统计数据失败')
  }
}

// ===== 渲染图表 =====
function renderCharts() {
  renderBarChart()
  renderPieChart()
}

function renderBarChart() {
  if (!barChartRef.value) return
  if (!barChart) barChart = echarts.init(barChartRef.value)
  const subjects = stats.value.subject_stats
  const isDark = document.documentElement.classList.contains('dark')

  barChart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 20, top: 30, bottom: 30 },
    xAxis: {
      type: 'category',
      data: subjects.map((s) => s.name),
      axisLabel: { color: isDark ? '#9ca3af' : '#606266' },
      axisLine: { lineStyle: { color: isDark ? '#374151' : '#dcdfe6' } },
    },
    yAxis: {
      type: 'value',
      max: 100,
      axisLabel: { color: isDark ? '#9ca3af' : '#606266' },
      splitLine: { lineStyle: { color: isDark ? '#374151' : '#f0f0f0' } },
    },
    series: [
      {
        name: '平均分',
        type: 'bar',
        data: subjects.map((s) => s.avg),
        barWidth: '45%',
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#6366f1' },
            { offset: 1, color: '#9294f5' },
          ]),
          borderRadius: [6, 6, 0, 0],
        },
        label: { show: true, position: 'top', color: isDark ? '#d1d5db' : '#606266' },
      },
    ],
  })
}

function renderPieChart() {
  if (!pieChartRef.value) return
  if (!pieChart) pieChart = echarts.init(pieChartRef.value)
  const dist = stats.value.distribution
  const isDark = document.documentElement.classList.contains('dark')

  pieChart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c} 人 ({d}%)' },
    legend: {
      bottom: 0,
      textStyle: { color: isDark ? '#9ca3af' : '#606266' },
    },
    color: ['#f56c6c', '#e6a23c', '#f9d976', '#67c23a', '#6366f1'],
    series: [
      {
        name: '分数段',
        type: 'pie',
        radius: ['40%', '65%'],
        center: ['50%', '45%'],
        avoidLabelOverlap: false,
        itemStyle: { borderRadius: 6, borderColor: 'transparent', borderWidth: 2 },
        label: { show: false },
        data: dist.map((d) => ({ name: d.label, value: d.count })),
      },
    ],
  })
}

// ===== 窗口大小变化时自适应 =====
function handleResize() {
  barChart?.resize()
  pieChart?.resize()
}

onMounted(() => {
  loadStats()
  window.addEventListener('resize', handleResize)
})

// AI 修改数据后自动刷新
watch(() => dataStore.refreshKey, () => loadStats())
// 切换到看板 Tab 时刷新
onActivated(() => {
  loadStats()
  // 主题切换后重绘（重新进入时也重绘，保证颜色正确）
  nextTick(() => renderCharts())
})

// ===== 统计卡片配置 =====
const cards = [
  { key: 'student_count', label: '学生总数', suffix: '人', color: '#6366f1', bg: 'rgba(99,102,241,0.12)' },
  { key: 'subject_count', label: '科目数量', suffix: '门', color: '#0ea5e9', bg: 'rgba(14,165,233,0.12)' },
  { key: 'score_count', label: '成绩记录', suffix: '条', color: '#10b981', bg: 'rgba(16,185,129,0.12)' },
  { key: 'avg_score', label: '平均分', suffix: '分', color: '#f59e0b', bg: 'rgba(245,158,11,0.12)' },
]
</script>

<template>
  <div>
    <h2 class="page-title">数据看板</h2>

    <!-- 统计卡片 -->
    <div class="stat-grid">
      <div v-for="card in cards" :key="card.key" class="stat-card">
        <div class="stat-icon" :style="{ background: card.bg, color: card.color }">
          <span class="stat-dot" :style="{ background: card.color }"></span>
        </div>
        <div class="stat-info">
          <div class="stat-label">{{ card.label }}</div>
          <div class="stat-value">
            {{ stats[card.key] }}<span class="stat-suffix">{{ card.suffix }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 补充指标 -->
    <div class="sub-metrics">
      <div class="metric-item">
        <span class="metric-label">及格率</span>
        <span class="metric-value">{{ stats.pass_rate }}%</span>
      </div>
      <div class="metric-item">
        <span class="metric-label">最高分</span>
        <span class="metric-value">{{ stats.max_score }}</span>
      </div>
      <div class="metric-item">
        <span class="metric-label">最低分</span>
        <span class="metric-value">{{ stats.min_score }}</span>
      </div>
    </div>

    <!-- 图表区 -->
    <div class="chart-grid">
      <div class="chart-card">
        <div class="chart-title">各科目平均分</div>
        <div ref="barChartRef" class="chart-body"></div>
      </div>
      <div class="chart-card">
        <div class="chart-title">成绩分布</div>
        <div ref="pieChartRef" class="chart-body"></div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 统计卡片 */
.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}
.stat-card {
  display: flex;
  align-items: center;
  gap: 16px;
  background: var(--app-card-bg);
  border-radius: 12px;
  padding: 20px;
  box-shadow: var(--app-card-shadow);
  transition: box-shadow 0.2s, transform 0.2s;
}
.stat-card:hover {
  box-shadow: var(--app-card-shadow-hover);
  transform: translateY(-2px);
}
.stat-icon {
  width: 52px;
  height: 52px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.stat-dot {
  width: 14px;
  height: 14px;
  border-radius: 50%;
}
.stat-info {
  min-width: 0;
}
.stat-label {
  font-size: 13px;
  color: var(--app-text-sub);
  margin-bottom: 4px;
}
.stat-value {
  font-size: 26px;
  font-weight: 600;
  color: var(--app-text-main);
  line-height: 1;
}
.stat-suffix {
  font-size: 13px;
  font-weight: 400;
  color: var(--app-text-sub);
  margin-left: 2px;
}

/* 补充指标 */
.sub-metrics {
  display: flex;
  gap: 24px;
  background: var(--app-card-bg);
  border-radius: 12px;
  padding: 16px 24px;
  margin-bottom: 16px;
  box-shadow: var(--app-card-shadow);
}
.metric-item {
  display: flex;
  align-items: center;
  gap: 8px;
}
.metric-label {
  font-size: 13px;
  color: var(--app-text-sub);
}
.metric-value {
  font-size: 16px;
  font-weight: 600;
  color: var(--el-color-primary);
}

/* 图表区 */
.chart-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.chart-card {
  background: var(--app-card-bg);
  border-radius: 12px;
  padding: 20px;
  box-shadow: var(--app-card-shadow);
}
.chart-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--app-text-main);
  margin-bottom: 12px;
}
.chart-body {
  height: 320px;
  width: 100%;
}

/* 响应式：窄屏时卡片和图表单列 */
@media (max-width: 900px) {
  .stat-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .chart-grid {
    grid-template-columns: 1fr;
  }
}
</style>
