"""12 接口测试 + 级联删除验证（依赖 init_data.py 的种子数据）"""
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)
ok_count = 0

def t(label, actual, expected, extra=''):
    global ok_count
    m = actual == expected
    if m: ok_count += 1
    print(f'  [{"OK" if m else "FAIL"}] {label} -> {actual} (expected {expected}) {extra}')

# ==================== Subjects (4) ====================
print('=== Subjects (4 APIs) ===')

r = client.get('/api/subjects')
t('GET  /api/subjects', r.status_code, 200, f'{len(r.json())} subs')

r = client.post('/api/subjects', json={'code': 'BIO', 'name': 'Biology'})
bio = r.json()
t('POST /api/subjects', r.status_code, 201, bio['name'])

r = client.put(f'/api/subjects/{bio["id"]}', json={'name': 'AdvBio'})
t('PUT  /api/subjects/{id}', r.status_code, 200, r.json()['name'])

r = client.delete(f'/api/subjects/{bio["id"]}')
t('DELETE /api/subjects/{id}', r.status_code, 204)

# ==================== Students (4) ====================
print('\n=== Students (4 APIs) ===')

r = client.get('/api/students?page=1&page_size=20')
d = r.json()
t('GET  /api/students?page=1&page_size=20', r.status_code, 200, f'total={d["total"]}')

r = client.post('/api/students', json={'student_id': '2024006', 'name': 'Test', 'gender': '男', 'age': 20})
sid = r.json()['student_id']
t('POST /api/students (201)', r.status_code, 201, sid)

r = client.post('/api/students', json={'student_id': '2024006', 'name': 'Dup', 'gender': '女', 'age': 21})
t('POST /api/students (409 dup)', r.status_code, 409, r.json()['detail'])

r = client.put(f'/api/students/{sid}', json={'name': 'Renamed', 'age': 21})
t('PUT  /api/students/{id}', r.status_code, 200, r.json()['name'])

# ==================== Cascade Delete ====================
print('\n=== Cascade Delete ===')

r = client.post('/api/scores', json={'student_id': sid, 'subject_id': 1, 'score': 88})
print(f'  [.] Recorded score: {r.status_code}')

r = client.delete(f'/api/students/{sid}')
t('DELETE /api/students (204)', r.status_code, 204)

r = client.get(f'/api/scores?student_id={sid}')
t('Cascade: scores cleared', len(r.json()), 0, f'{len(r.json())} remain')

# ==================== Scores (4) ====================
print('\n=== Scores (4 APIs) ===')

r = client.get('/api/scores?student_id=2024001')
t('GET  /api/scores?student_id=2024001', r.status_code, 200, f'{len(r.json())} sc')

# 创建临时科目来测新增成绩
import time
code = f'TMP{int(time.time())}'
r = client.post('/api/subjects', json={'code': code, 'name': 'TmpSub'})
tmp = r.json()

r = client.post('/api/scores', json={'student_id': '2024002', 'subject_id': tmp['id'], 'score': 99})
t('POST /api/scores (201)', r.status_code, 201, f'score={r.json()["score"]}')

r = client.post('/api/scores', json={'student_id': '2024002', 'subject_id': tmp['id'], 'score': 80})
t('POST /api/scores (409 UNIQUE)', r.status_code, 409, r.json()['detail'])

r = client.put('/api/scores/1', json={'score': 86})
t('PUT  /api/scores/1', r.status_code, 200, f'-> {r.json()["score"]}')

# 找并删除临时成绩
r = client.get('/api/scores?student_id=2024002')
for sc in r.json():
    if sc['subject_name'] == 'TmpSub':
        r2 = client.delete(f'/api/scores/{sc["id"]}')
        t('DELETE /api/scores/{id}', r2.status_code, 204)
        break

client.delete(f'/api/subjects/{tmp["id"]}')

print(f'\n{"=" * 40}')
print(f'  Total: {ok_count}/14 passed')
print(f'{"=" * 40}')
print('ALL PASS!' if ok_count == 14 else f'{14 - ok_count} FAILED!')
