<script setup>
/**
 * AIQuery.vue —— AI 智能体对话页（ReAct Agent）
 * 思考过程折叠隐藏，查询结果用表格展示
 */
defineOptions({ name: 'AIQuery' })
import { ref, nextTick } from 'vue'
import { useDataStore } from '../stores/dataStore'

const dataStore = useDataStore()
const query = ref('')
const loading = ref(false)
const messages = ref([])
const chatArea = ref(null)

const examples = ['你好', '数学不及格的学生有哪些', '各科目平均分排名']

const colMap = {
  student_id: '学号', name: '姓名', gender: '性别', age: '年龄',
  subject_name: '科目', score: '分数', avg_score: '平均分', total_score: '总分',
  count: '数量', max_score: '最高分', min_score: '最低分',
  pass_count: '及格人数', fail_count: '不及格人数',
}
function colLabel(col) { return colMap[col] || col }

function setExample(text) { query.value = text; handleQuery() }
function scrollToBottom() { nextTick(() => { if (chatArea.value) chatArea.value.scrollTop = chatArea.value.scrollHeight }) }

async function handleQuery() {
  const q = query.value.trim()
  if (!q || loading.value) return
  query.value = ''
  loading.value = true
  messages.value.push({ role: 'user', text: q })
  scrollToBottom()
  const aiMsg = { role: 'ai', steps: [], text: '', status: 'thinking', showThinking: false }
  messages.value.push(aiMsg)
  scrollToBottom()
  try {
    const resp = await fetch(`/api/ai/query?q=${encodeURIComponent(q)}`)
    await handleSSE(resp.body.getReader(), aiMsg)
  } catch { aiMsg.text = '连接失败，请重试。'; aiMsg.status = 'error' }
  finally { loading.value = false }
}

async function confirmAction(msg) {
  msg.status = 'thinking'
  loading.value = true
  try {
    const r = await fetch(`/api/ai/query?q=${encodeURIComponent('确认')}`)
    await handleSSE(r.body.getReader(), msg)
  } catch { msg.text = '执行失败'; msg.status = 'error' }
  loading.value = false
}

function cancelAction(msg) {
  msg.steps.push({ type: 'cancel', content: '已取消' })
  msg.status = 'done'; msg.text = '已取消。'
  fetch(`/api/ai/query?q=${encodeURIComponent('取消')}`).catch(() => {})
}

async function handleSSE(reader, msg) {
  const d = new TextDecoder(); let buf = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += d.decode(value, { stream: true })
    const lines = buf.split('\n'); buf = lines.pop() || ''
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      try { handleEvent(JSON.parse(line.slice(6)), msg) } catch {}
    }
  }
}

function handleEvent(event, msg) {
  const evt = event.event
  switch (evt) {
    case 'agent_thinking':
      msg.steps.push({ type: 'thinking', content: event.message })
      break
    case 'agent_step':
      msg.steps.push({
        type: 'step',
        thought: event.thought,
        tool: event.tool,
        observation: event.observation,
        tableData: event.tableData,
        tableCount: event.tableCount || 0,
      })
      break
    case 'confirm_required':
      msg.text = event.summary || '需要确认'
      msg.status = 'confirm'
      msg.thought = event.thought
      break
    case 'agent_ask':
      msg.text = event.question || '请回复'
      msg.status = 'done'
      break
    case 'data_changed':
      dataStore.notifyChange()
      break
    case 'error':
      msg.text = event.message || '出错了'
      msg.status = 'error'
      break
    case 'done':
      msg.text = event.summary || event.message || ''
      msg.status = 'done'
      if (event.type === 'write_result') dataStore.notifyChange()
      break
    case 'executing':
      msg.steps.push({ type: 'executing', content: event.message })
      break
  }
  scrollToBottom()
}

const toolNameMap = {
  query_db: '查询数据库', modify_db: '修改数据库',
  check_exists: '检查是否存在', ask_user: '向用户提问',
}
function toolLabel(name) { return toolNameMap[name] || name }
</script>

<template>
  <div class="ai-chat">
    <div class="chat-messages" ref="chatArea">
      <div v-if="messages.length === 0" class="empty-state">
        <div class="empty-icon">🤖</div>
        <div class="empty-title">你好！我是成绩管理智能体</div>
      </div>

      <div v-for="(msg, i) in messages" :key="i" :class="['message-row', msg.role]">
        <!-- 用户 -->
        <div v-if="msg.role === 'user'" class="message-bubble user-bubble">
          <div class="msg-text">{{ msg.text }}</div>
        </div>

        <!-- AI -->
        <div v-else class="ai-message">
          <!-- 思考中动画 -->
          <div v-if="msg.status === 'thinking'" class="thinking-dots">
            <span></span><span></span><span></span>
          </div>

          <!-- 最终回复 -->
          <div v-if="msg.text && msg.status !== 'thinking'" class="message-bubble ai-bubble">
            <div class="msg-text">{{ msg.text }}</div>
          </div>

          <!-- 确认按钮 -->
          <div v-if="msg.status === 'confirm'" class="confirm-buttons">
            <el-button size="small" type="primary" @click="confirmAction(msg)">确认</el-button>
            <el-button size="small" @click="cancelAction(msg)">取消</el-button>
          </div>

          <!-- 错误 -->
          <div v-if="msg.status === 'error'" class="error-tag">出错了</div>

          <!-- 查询结果表格 -->
          <div v-for="(step, si) in msg.steps" :key="'tbl'+si">
            <div v-if="step.tableData?.length" class="data-table">
              <div class="table-header">共 {{ step.tableCount || step.tableData.length }} 条</div>
              <el-table :data="step.tableData" style="width:100%" stripe border max-height="280" size="small">
                <el-table-column
                  v-for="col in Object.keys(step.tableData[0])"
                  :key="col" :prop="col" :label="colLabel(col)" min-width="90"
                />
              </el-table>
            </div>
          </div>

          <!-- 思考过程（折叠） —— 只在完成后才显示 -->
          <div v-if="msg.status !== 'thinking' && msg.steps?.length" class="thinking-toggle" @click="msg.showThinking = !msg.showThinking">
            <span class="toggle-icon">{{ msg.showThinking ? '▼' : '▶' }}</span>
            <span class="toggle-label">思考过程 ({{ msg.steps.length }} 步)</span>
          </div>

          <div v-if="msg.showThinking && msg.status !== 'thinking'" class="thought-chain">
            <div v-for="(step, si) in msg.steps" :key="si" :class="['step-item', step.type]">
              <div v-if="step.type === 'thinking'" class="step-thinking">
                💭 {{ step.content }}
              </div>
              <div v-else-if="step.type === 'executing'" class="step-executing">
                ⚡ {{ step.content }}
              </div>
              <div v-else-if="step.type === 'step'" class="step-tool">
                <div class="step-thought">💭 {{ step.thought }}</div>
                <div class="step-action">🔧 {{ toolLabel(step.tool) }}</div>
                <div class="step-obs">📋 {{ step.observation }}</div>
              </div>
              <div v-else-if="step.type === 'cancel'" class="step-cancel">
                ❌ {{ step.content }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 快捷示例 -->
    <div class="quick-examples">
      <el-button v-for="ex in examples" :key="ex" size="small" plain @click="setExample(ex)">{{ ex }}</el-button>
    </div>

    <!-- 输入区 -->
    <div class="chat-input">
      <el-input v-model="query" placeholder="输入你的问题..." clearable :disabled="loading" @keyup.enter="handleQuery" />
      <el-button type="primary" :loading="loading" @click="handleQuery">发送</el-button>
    </div>
  </div>
</template>

<style scoped>
.ai-chat { display: flex; flex-direction: column; height: calc(100vh - 120px); }
.chat-messages { flex: 1; overflow-y: auto; padding: 16px 0; }
.message-row { margin-bottom: 18px; }
.message-row.user { display: flex; justify-content: flex-end; }
.message-bubble { display: inline-block; padding: 10px 14px; border-radius: 12px; font-size: 14px; line-height: 1.6; word-break: break-word; }
.user-bubble { background: #409eff; color: #fff; max-width: 70%; }
.ai-bubble { background: #f0f2f5; color: #303133; max-width: 85%; margin-bottom: 4px; }

/* 表格 */
.data-table { margin: 8px 0 12px 0; max-width: 100%; }
.table-header { font-size: 12px; color: #909399; margin-bottom: 4px; }

/* 思考过程切换 */
.thinking-toggle {
  cursor: pointer; padding: 4px 0; font-size: 12px; color: #909399;
  user-select: none; display: flex; align-items: center; gap: 4px;
  opacity: 0.7; transition: opacity 0.2s;
}
.thinking-toggle:hover { opacity: 1; }
.toggle-icon { font-size: 10px; width: 12px; }
.toggle-label { font-size: 12px; }

/* 思考链 */
.thought-chain { margin-top: 4px; padding-left: 8px; border-left: 2px solid #e4e7ed; }
.step-item { padding: 4px 0; font-size: 12px; }
.step-thought { color: #606266; }
.step-action { color: #409eff; }
.step-obs { color: #67c23a; }
.step-thinking { color: #909399; }
.step-executing { color: #e6a23c; }
.step-cancel { color: #909399; }

.thinking-dots { padding: 8px 0; }
.thinking-dots span { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #909399; margin: 0 3px; animation: blink 1.4s infinite; }
.thinking-dots span:nth-child(2) { animation-delay: 0.2s; }
.thinking-dots span:nth-child(3) { animation-delay: 0.4s; }
@keyframes blink { 0%, 100% { opacity: 0.2; } 50% { opacity: 1; } }

.confirm-buttons { margin-top: 8px; display: flex; gap: 8px; }
.error-tag { color: #f56c6c; font-size: 12px; margin-top: 4px; }
.ai-message { max-width: 95%; }

.empty-state { text-align: center; padding: 60px 20px; }
.empty-icon { font-size: 48px; margin-bottom: 12px; }
.empty-title { font-size: 16px; color: #303133; margin-bottom: 8px; }
.empty-sub { font-size: 13px; color: #909399; }
.quick-examples { display: flex; gap: 8px; padding: 8px 0; flex-wrap: wrap; border-top: 1px solid #ebeef5; }
.chat-input { display: flex; gap: 8px; padding: 8px 0; border-top: 1px solid #ebeef5; }
</style>
