# 葫芦侠收藏帖子 API 文档

## 功能说明

本功能允许你获取指定用户在葫芦侠三楼的收藏帖子列表。

## API 接口

### 1. 登录 (必需)

在获取收藏列表之前，需要先登录。

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

### 2. 获取收藏列表

**端点**: `GET /api/favorites`

**查询参数**:
- `userid` (必需): 要查询的用户ID
- `count` (可选): 获取数量，默认20，最大100
- `start` (可选): 起始位置，默认0（用于分页）

**示例请求**:
```
GET /api/favorites?userid=123456&count=20&start=0
```

**成功响应**:
```json
{
  "success": true,
  "code": 200,
  "msg": [
    {
      "postID": "12345678",
      "title": "帖子标题",
      "category": {
        "categoryID": "57",
        "title": "板块名称"
      },
      "createTime": 1234567890000,
      "detail": "帖子内容摘要",
      "user": {
        "userID": "123456",
        "nick": "发帖用户昵称"
      }
    }
  ],
  "total": 20
}
```

**失败响应**:
```json
{
  "success": false,
  "code": 401,
  "msg": "未登录，请先登录"
}
```

## 使用示例

### Python 示例

```python
import requests

BASE_URL = "http://localhost:5000"

# 1. 登录
login_resp = requests.post(f"{BASE_URL}/api/login", json={
    "account": "your_account",
    "password": "your_password"
})
print(login_resp.json())

# 2. 获取收藏列表
favorites_resp = requests.get(f"{BASE_URL}/api/favorites", params={
    "userid": "123456",
    "count": 20
})
result = favorites_resp.json()

if result["success"]:
    for fav in result["msg"]:
        print(f"帖子ID: {fav['postID']}")
        print(f"标题: {fav['title']}")
        print(f"板块: {fav['category']['title']}")
        print("-" * 50)
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

// 2. 获取收藏列表
async function getFavorites(userId, count = 20) {
  const resp = await fetch(
    `${BASE_URL}/api/favorites?userid=${userId}&count=${count}`
  );
  return await resp.json();
}

// 使用
login().then(result => {
  if (result.success) {
    getFavorites("123456", 20).then(data => {
      if (data.success) {
        data.msg.forEach(fav => {
          console.log(`帖子ID: ${fav.postID}`);
          console.log(`标题: ${fav.title}`);
          console.log(`板块: ${fav.category.title}`);
        });
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

# 2. 获取收藏列表
curl "http://localhost:5000/api/favorites?userid=123456&count=20"
```

## 返回的帖子数据结构

每条收藏帖子包含以下字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `postID` | string | 帖子ID |
| `title` | string | 帖子标题 |
| `detail` | string | 帖子内容 |
| `category` | object | 所属板块信息 |
| `category.categoryID` | string | 板块ID |
| `category.title` | string | 板块名称 |
| `user` | object | 发帖用户信息 |
| `user.userID` | string | 用户ID |
| `user.nick` | string | 用户昵称 |
| `createTime` | number | 收藏时间戳（毫秒） |

## 注意事项

1. **必须先登录**: 获取收藏列表前必须先调用登录接口
2. **会话保持**: 登录状态会保持在服务器端，直到应用重启
3. **权限限制**: 只能查看自己或公开的用户的收藏列表
4. **分页查询**: 使用 `start` 和 `count` 参数进行分页
5. **API限制**: 建议每次请求不超过100条，避免超时

## 错误代码

| 代码 | 说明 |
|------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 401 | 未登录或登录已过期 |
| 403 | 无权限访问 |
| 500 | 服务器内部错误 |

## 测试

运行提供的测试脚本：

```bash
# 编辑 test_favorites.py，填入你的账号密码和要查询的用户ID
python test_favorites.py
```

## 技术实现

本功能调用了葫芦侠官方 API：

- **API路径**: `/favorite/list`
- **API版本**: `4.1.8`
- **请求方式**: GET
- **基础URL**: `http://floor.huluxia.com`

完整的请求URL格式：
```
http://floor.huluxia.com/favorite/list/ANDROID/4.1.8?userid=123456&count=20&start=0&_key=登录令牌&...其他参数
```

## 与网站 API 的对比

参考的网站 (https://hlx.7yan.net) 使用类似的逻辑：

1. 前端发送请求到 `./api/postid.php?action=getfavorites&userid=xxx&count=xxx`
2. PHP 后端转发请求到葫芦侠官方 API
3. 返回格式化后的数据给前端

本项目直接在 Python 后端实现了相同的功能，无需中间 PHP 层。
