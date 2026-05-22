# 用户认证模块设计

> 里程碑：MVP 最小账号系统
> 状态：待实施
> 分支：`feat/user-auth-worklog`

## 1. 目标

给系统加上用户注册/登录，所有写操作绑定真实身份，替代现有的"自报家门"模式。

**不含**：工作量统计、管理后台、权限分级（后续迭代）。

## 2. 技术选型

| 组件 | 选型 | 理由 |
|------|------|------|
| 密码哈希 | `passlib[bcrypt]` | 行业标准，一行调用 |
| Token | `PyJWT` + HS256 | 轻量，无外部依赖 |
| Token 传输 | `Authorization: Bearer <jwt>` | RESTful 标准 |
| Token 存储（前端） | `localStorage` | MVP 够用，避免 cookie 跨域问题 |
| 会话状态（前端） | React Context | 最简方案，不需要 Redux |

## 3. 数据模型变更

### 3.1 User 表扩展

现有模型（`govdoc/db/models.py`）：

```python
class User(SQLModel, table=True):
    id: str = Field(default_factory=uid, primary_key=True)
    username: str
    display_name: str
    role: str = "reviewer"
```

变更后：

```python
class User(SQLModel, table=True):
    id: str = Field(default_factory=uid, primary_key=True)
    username: str = Field(unique=True, index=True)
    password_hash: str
    display_name: str
    role: str = "reviewer"
    is_active: bool = True
```

| 新增字段 | 类型 | 说明 |
|----------|------|------|
| `password_hash` | `str` | bcrypt 哈希，**不允许**存明文 |
| `is_active` | `bool` | 软禁用开关，预留管理功能 |

| 变更字段 | 说明 |
|----------|------|
| `username` | 加 `unique=True` + `index=True`，登录时用于查找 |

### 3.2 Alembic 迁移

需要注意：
- `password_hash` 是 NOT NULL 字段，但现有 `User` 表可能为空或有存量数据
- 迁移策略：先加 `password_hash` 为 nullable → 存量用户设默认值 → 再改回 NOT NULL
- 如果 User 表当前无数据（极可能），可以直接加 NOT NULL + default placeholder

## 4. 后端 API 设计

### 4.1 新增路由：`govdoc/api/routes/auth.py`

#### `POST /api/v1/auth/register`

注册新用户。

```python
# 请求体
{
    "username": "zhangsan",
    "password": "明文密码",
    "display_name": "张三"
}

# 响应 201
{
    "id": "abc123",
    "username": "zhangsan",
    "display_name": "张三",
    "role": "reviewer"
}
```

校验规则：
- `username`：3-32 字符，唯一
- `password`：最少 6 字符
- `display_name`：非空

#### `POST /api/v1/auth/login`

```python
# 请求体
{
    "username": "zhangsan",
    "password": "明文密码"
}

# 响应 200
{
    "access_token": "eyJhbGciOi...",
    "token_type": "bearer",
    "user": {
        "id": "abc123",
        "username": "zhangsan",
        "display_name": "张三",
        "role": "reviewer"
    }
}
```

Token payload（JWT）：
```json
{
    "sub": "user_id",
    "username": "zhangsan",
    "exp": 1700000000
}
```

Token 有效期：**24 小时**（MVP 阶段，不做 refresh token）。

#### `GET /api/v1/auth/me`

需要 Bearer token。返回当前用户信息。

```python
# 响应 200
{
    "id": "abc123",
    "username": "zhangsan",
    "display_name": "张三",
    "role": "reviewer"
}
```

### 4.2 认证依赖：`govdoc/api/deps.py`

新增 `get_current_user`：

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from sqlmodel import Session, select

from govdoc.db.models import User
from govdoc.config import load_config

security = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: Session = Depends(get_db_session),
) -> User:
    """从 Bearer token 解析当前用户。"""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="无效或过期的 token")

    user = session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="用户不存在或已禁用")
    return user
```

### 4.3 路由鉴权接入

**策略：写操作鉴权，读操作开放。**

每个路由文件中，在写操作函数签名加 `current_user: User = Depends(get_current_user)`：

```python
# 接入前
@router.post("/projects")
def create_project(payload: CreateProjectRequest, session: Session = Depends(get_db_session)):
    ...
    project = Project(name=payload.name, created_by=payload.created_by)

# 接入后
@router.post("/projects")
def create_project(
    payload: CreateProjectRequest,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    ...
    project = Project(name=payload.name, created_by=current_user.username)
```

核心替换点：

| 路由文件 | 需鉴权的操作 | 替换的硬编码字段 |
|----------|-------------|-----------------|
| `projects.py` | `create_project`, `upload_tender_doc` | `created_by` → `current_user.username` |
| `audit.py` | `create_audit_run`, `cancel_audit_run` | `created_by="system"` → `current_user.username` |
| `checkpoints.py` | `update_checkpoint`, `delete_checkpoint` | `modified_by` → `current_user.username` |
| `workpapers.py` | `update_workpaper_draft`, `finalize_workpaper` | `approved_by` → `current_user.username` |
| `comments.py` | `create_comment`, `delete_comment` | `author=payload.author` → `current_user.username` |
| `rules.py` | `upload_rule` | 无显式 actor，加 `log_activity` 的 actor |

### 4.4 JWT Secret 配置

在 `.env` 中新增：

```bash
JWT_SECRET_KEY=<随机字符串>
JWT_EXPIRE_HOURS=24
```

`govdoc/config.py` 的 `AppConfig` 新增字段：

```python
jwt_secret_key: str = "change-me-in-production"
jwt_expire_hours: int = 24
```

## 5. 前端设计

### 5.1 认证状态管理：`src/context/AuthContext.tsx`

```typescript
interface AuthState {
    token: string | null;
    user: { id: string; username: string; display_name: string; role: string } | null;
    isAuthenticated: boolean;
    login: (username: string, password: string) => Promise<void>;
    register: (username: string, password: string, displayName: string) => Promise<void>;
    logout: () => void;
}
```

- 初始化时从 `localStorage` 读 token
- 有 token → 调 `/auth/me` 验证并恢复用户信息
- `logout()` 清空 localStorage + 状态

### 5.2 登录页：`src/pages/LoginPage.tsx`

- 用户名 + 密码表单
- "注册"链接（切换到注册模式或跳转）
- 登录成功 → 跳转 `/`（工作台总览）

### 5.3 注册页：`src/pages/RegisterPage.tsx`

- 用户名 + 密码 + 确认密码 + 显示名
- 注册成功 → 自动登录 → 跳转 `/`

### 5.4 API 拦截器：`src/api/v3.ts`

修改 `request()` 函数：

```typescript
export async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const base = resolveBaseUrl();
    const token = localStorage.getItem("token");

    const headers = new Headers(init?.headers);
    if (token) {
        headers.set("Authorization", `Bearer ${token}`);
    }

    const res = await fetch(`${base}${path}`, { ...init, headers });

    // 401 → 清空 token，跳转登录页
    if (res.status === 401) {
        localStorage.removeItem("token");
        window.location.href = "/login";
        throw new Error("登录已过期");
    }

    // ... 其余不变
}
```

### 5.5 路由守卫：`src/App.tsx`

```tsx
<Routes>
    <Route path="/login" element={<LoginPage />} />
    <Route path="/register" element={<RegisterPage />} />
    <Route element={<RequireAuth><AppShell /></RequireAuth>}>
        {/* 现有业务路由不变 */}
    </Route>
</Routes>
```

`RequireAuth` 组件：检查 AuthContext.isAuthenticated，false → `<Navigate to="/login" />`。

### 5.6 Sidebar 用户信息

在 Sidebar 底部区域替换现有"系统正常运行"提示：

```
┌─────────────────────┐
│ 🟢 张三 (reviewer)   │
│    [退出登录]         │
└─────────────────────┘
```

## 6. 文件变更清单

### 后端

| 文件 | 操作 | 内容 |
|------|------|------|
| `pyproject.toml` | MODIFY | + `PyJWT`, `passlib[bcrypt]` |
| `govdoc/config.py` | MODIFY | AppConfig + `jwt_secret_key`, `jwt_expire_hours` |
| `govdoc/db/models.py` | MODIFY | User + `password_hash`, `is_active`, `username` unique |
| `govdoc/api/deps.py` | MODIFY | + `get_current_user` |
| `govdoc/api/routes/auth.py` | **NEW** | register / login / me |
| `govdoc/api/main.py` | MODIFY | + `auth_router` |
| `govdoc/api/routes/projects.py` | MODIFY | 写操作 + Depends |
| `govdoc/api/routes/audit.py` | MODIFY | 写操作 + Depends |
| `govdoc/api/routes/checkpoints.py` | MODIFY | 写操作 + Depends |
| `govdoc/api/routes/workpapers.py` | MODIFY | 写操作 + Depends |
| `govdoc/api/routes/comments.py` | MODIFY | 写操作 + Depends |
| `govdoc/api/routes/rules.py` | MODIFY | 写操作 + Depends |
| Alembic 迁移 | **NEW** | User 表字段变更 |

### 前端

| 文件 | 操作 | 内容 |
|------|------|------|
| `src/context/AuthContext.tsx` | **NEW** | 认证状态管理 |
| `src/pages/LoginPage.tsx` | **NEW** | 登录页 |
| `src/pages/RegisterPage.tsx` | **NEW** | 注册页 |
| `src/api/v3.ts` | MODIFY | token 拦截器 + auth API |
| `src/App.tsx` | MODIFY | 路由守卫 + auth 路由 |
| `src/components/Sidebar.tsx` | MODIFY | 用户信息 + 退出按钮 |

## 7. 实施顺序

```
Phase 1: 后端基础（可独立测试）
  ├─ 1.1 pyproject.toml 加依赖 + pip install
  ├─ 1.2 config.py 加 JWT 配置
  ├─ 1.3 User 模型扩展 + Alembic 迁移
  ├─ 1.4 auth.py 路由（register/login/me）
  └─ 1.5 deps.py get_current_user

Phase 2: 后端鉴权接入
  ├─ 2.1 所有写路由加 Depends(get_current_user)
  ├─ 2.2 替换硬编码 actor → current_user.username
  └─ 2.3 Swagger 测试验证

Phase 3: 前端
  ├─ 3.1 AuthContext + v3.ts 拦截器
  ├─ 3.2 LoginPage + RegisterPage
  ├─ 3.3 App.tsx 路由守卫
  ├─ 3.4 Sidebar 用户信息
  └─ 3.5 浏览器端到端验证
```

## 8. 安全注意事项

| 事项 | 做法 |
|------|------|
| 密码存储 | bcrypt hash，**禁止**明文 |
| JWT Secret | 生产环境必须从 `.env` 读取，不能用默认值 |
| 密码传输 | HTTPS（部署层配置，MVP 先不管） |
| Token 过期 | 24h 自动过期，前端 401 跳登录 |
| 注册防刷 | MVP 不做，后续可加 rate limit |
| username 唯一 | DB unique 约束 + API 层检查 |
