# 葫芦侠赠送葫芦功能 API 文档

## 功能说明

本功能允许你获取帖子的评论列表，并批量赠送葫芦（打赏）给指定评论。

---

## API 接口

### 1. 登录 (必需)

在使用任何功能之前，需要先登录。

**端点**: `POST /api/login`

**请求体**:
```json
{
  "account": "你的账号",
  "password": "你的密码"
}
```

**响应**:
```json
{
  "success": true,
  "msg": "登录成功",
  "nick": "用户昵称",
  "uid": "用户ID",
  "token": "登录令牌"
}
```

---

### 2. 获取评论列表

**端点**: `GET /api/comments`

**查询参数**:
- `post_id` (必需): 帖子ID

**示例请求**:
```
GET /api/comments?post_id=12345678
```

**成功响应**:
```json
{
  "success": true,
  "code": 200,
  "comments": [
    {
      "commentID": "123456789",
      "text": "评论内容",
      "user": {
        "userID": "123456",
        "nick": "用户昵称",
        "avatar": "头像URL"
      },
      "createTime": 1634567890000
    }
  ],
  "total": 50
}
```

---

### 3. 单次赠送葫芦

**端点**: `POST /api/give_score_single`

**请求体**:
```json
{
  "comment_id": "123456789",
  "score": 5,
  "score_txt": "赠送留言"
}
```

**参数说明**:
- `comment_id` (必需): 评论ID
- `score` (必需): 赠送数量
- `score_txt` (可选): 留言，默认"赠送"

**成功响应**:
```json
{
  "success": true,
  "code": 200,
  "msg": "赠送成功"
}
```

---

### 4. 批量赠送葫芦 (SSE)

**端点**: `POST /api/give_score_batch`

**请求体**:
```json
{
  "comment_id": "123456789",
  "total": 520,
  "per_score": 5,
  "score_txt": "奖励发放 辛苦了",
  "delay_ms": 1000
}
```

**参数说明**:
- `comment_id` (必需): 评论ID
- `total` (必需): 总共要赠送的葫芦数量
- `per_score` (可选): 每次赠送的数量，默认5
- `score_txt` (可选): 留言，默认"赠送"
- `delay_ms` (可选): 每次赠送之间的延迟（毫秒），默认1000

**响应格式**: Server-Sent Events (SSE)

实时流式响应，每条消息格式：
```
event: log
data: {"msg": "正在赠送第 1/104 次，数量: 5"}

event: log
data: {"msg": "✓ 第 1 次赠送成功"}

...

event: complete
data: {"sent": 520, "total": 520, "msg": "🎉 完成！共赠送 520 葫芦"}
```

---

## 使用示例

### Python 示例

```python
import requests
import json

BASE_URL = "http://localhost:5000"

# 1. 登录
login_resp = requests.post(f"{BASE_URL}/api/login", json={
    "account": "your_account",
    "password": "your_password"
})
print(login_resp.json())

# 2. 获取评论列表
comments_resp = requests.get(f"{BASE_URL}/api/comments", params={
    "post_id": "12345678"
})
comments_data = comments_resp.json()

if comments_data["success"]:
    for comment in comments_data["comments"][:5]:
        print(f"评论ID: {comment['commentID']}")
        print(f"用户: {comment['user']['nick']}")
        print(f"内容: {comment['text']}")
        print("-" * 50)

# 3. 单次赠送
give_resp = requests.post(f"{BASE_URL}/api/give_score_single", json={
    "comment_id": "123456789",
    "score": 10,
    "score_txt": "感谢分享"
})
print(give_resp.json())

# 4. 批量赠送（SSE流式响应）
batch_resp = requests.post(f"{BASE_URL}/api/give_score_batch",
    json={
        "comment_id": "123456789",
        "total": 520,
        "per_score": 5,
        "score_txt": "奖励发放 辛苦了"
    },
    stream=True
)

for line in batch_resp.iter_lines():
    if line:
        line_str = line.decode('utf-8')
        if line_str.startswith('data:'):
            data = json.loads(line_str[5:].strip())
            print(data.get('msg'))
```

### JavaScript 示例

```javascript
const BASE_URL = "http://localhost:5000";

// 1. 登录
async function login() {
  const resp = await fetch(`${BASE_URL}/api/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      account: "your_account",
      password: "your_password"
    })
  });
  return await resp.json();
}

// 2. 获取评论列表
async function getComments(postId) {
  const resp = await fetch(`${BASE_URL}/api/comments?post_id=${postId}`);
  return await resp.json();
}

// 3. 单次赠送
async function giveScore(commentId, score, text) {
  const resp = await fetch(`${BASE_URL}/api/give_score_single`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      comment_id: commentId,
      score: score,
      score_txt: text
    })
  });
  return await resp.json();
}

// 4. 批量赠送（SSE）
function giveScoreBatch(commentId, total, perScore, text) {
  const params = new URLSearchParams({
    comment_id: commentId,
    total: total,
    per_score: perScore,
    score_txt: text
  });

  const eventSource = new EventSource(`${BASE_URL}/api/give_score_batch?${params}`);

  eventSource.onmessage = (e) => {
    const data = JSON.parse(e.data);
    console.log(data.msg);

    if (data.type === 'final' || data.type === 'error') {
      eventSource.close();
    }
  };

  eventSource.onerror = () => {
    eventSource.close();
  };
}

// 使用
login().then(result => {
  if (result.success) {
    getComments("12345678").then(data => {
      if (data.success && data.comments.length > 0) {
        const firstComment = data.comments[0];
        console.log(`评论ID: ${firstComment.commentID}`);

        // 单次赠送
        giveScore(firstComment.commentID, 10, "感谢分享");

        // 或批量赠送
        // giveScoreBatch(firstComment.commentID, 520, 5, "奖励发放");
      }
    });
  }
});
```

### cURL 示例

```bash
# 1. 登录
curl -X POST http://localhost:5000/api/login \
  -H "Content-Type: application/json" \
  -d '{"account":"your_account","password":"your_password"}'

# 2. 获取评论列表
curl "http://localhost:5000/api/comments?post_id=12345678"

# 3. 单次赠送
curl -X POST http://localhost:5000/api/give_score_single \
  -H "Content-Type: application/json" \
  -d '{"comment_id":"123456789","score":10,"score_txt":"感谢分享"}'

# 4. 批量赠送（SSE流）
curl -X POST http://localhost:5000/api/give_score_batch \
  -H "Content-Type: application/json" \
  -d '{"comment_id":"123456789","total":520,"per_score":5,"score_txt":"奖励发放"}' \
  --no-buffer
```

---

## 工作原理

### 批量赠送逻辑

批量赠送功能会自动计算需要赠送的次数：

```
总次数 = 向上取整(总额 / 单次数量)

例如：
- 总额 520，单次 5 → 需要 104 次
- 总额 100，单次 10 → 需要 10 次
- 总额 50，单次 7 → 需要 8 次（最后一次只赠送 1）
```

每次赠送之间会有延迟（默认1秒），避免频率限制。

---

## 技术实现

### 调用的葫芦侠官方 API

#### 获取评论列表
- **路径**: `/post/detail/ANDROID/4.1.8`
- **方法**: GET
- **参数**: `post_id`, `_key`, 其他标准参数

#### 赠送葫芦
- **路径**: `/score/give/ANDROID/4.1.8`
- **方法**: GET
- **参数**:
  - `_key`: 登录令牌
  - `comment_id`: 评论ID
  - `score`: 赠送数量
  - `score_txt`: 留言
  - `sign`: 签名（MD5）
  - 其他标准参数

### 签名算法

```python
SIGN_TAGS = ["_key", "comment_id", "device_code", "score", "score_txt"]
SECRET_KEY = "fa1c28a5b62e79c3e63d9030b6142e4b"

def sign(params):
    raw = ""
    for tag in SIGN_TAGS:
        raw += tag + params.get(tag, "")
    raw += SECRET_KEY
    return hashlib.md5(raw.encode('utf-8')).hexdigest()
```

---

## 注意事项

1. **必须先登录**: 所有功能都需要先登录获取 `_key`
2. **会话保持**: 登录状态保持在服务器端
3. **延迟设置**: 建议每次赠送之间至少间隔1秒
4. **频率限制**: 过快的请求可能被葫芦侠限制
5. **葫芦消耗**: 赠送操作会实际消耗你的葫芦
6. **权限验证**: 只能赠送给存在的评论

---

## 错误代码

| 代码 | 说明 |
|------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 401 | 未登录或登录已过期 |
| 500 | 服务器内部错误 |

---

## 测试

运行提供的测试脚本：

```bash
# 编辑 test_give_score.py，填入你的账号密码和帖子ID
python test_give_score.py
```

---

## 完整功能列表

你的项目现在支持：

✅ 登录认证
✅ 发布帖子
✅ 发布评论
✅ 签到
✅ **获取收藏列表** (新)
✅ **获取评论列表** (新)
✅ **单次赠送葫芦** (新)
✅ **批量赠送葫芦** (新)

---

## 参考

- 目标网站: https://tk.27xk.cn/hlx/gourd.php
- 逆向分析报告: `E:\hlxtool\hlx-analysis\GOURD_ANALYSIS_REPORT.md`
- 测试脚本: `E:\hlx-web-py\test_give_score.py`
