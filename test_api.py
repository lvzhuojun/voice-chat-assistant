# -*- coding: utf-8 -*-
"""
Voice Chat Assistant - Complete API functional test script
Tests all REST endpoints, auth flow, conversation management, voice management
"""

import sys
import io
import httpx

# Force UTF-8 output on Windows (avoid GBK encode errors)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = "http://127.0.0.1:8000"
PASS_COUNT = 0
FAIL_COUNT = 0


def ok(label, detail=""):
    global PASS_COUNT
    PASS_COUNT += 1
    print(f"  [OK] {label}" + (f" -- {detail}" if detail else ""))


def fail(label, detail=""):
    global FAIL_COUNT
    FAIL_COUNT += 1
    print(f"  [FAIL] {label}" + (f" -- {detail}" if detail else ""))


def section(title):
    print(f"\n{'='*55}")
    print(f"  {title}")
    print(f"{'='*55}")


def check(label, condition, detail=""):
    if condition:
        ok(label, detail)
    else:
        fail(label, detail)


def run_tests():
    client = httpx.Client(base_url=BASE, timeout=15.0)
    token = None
    conv_id = None

    # ──────────────────────────────────────────────────────────
    section("1. 基础健康检查")
    # ──────────────────────────────────────────────────────────
    try:
        r = client.get("/api/health")
        d = r.json()
        check("健康检查返回 200", r.status_code == 200)
        check("status == ok", d.get("status") == "ok")
        check("GPU 信息存在", "gpu" in d, str(d.get("gpu", {}).get("name", "N/A")))
        check("Whisper 已加载", d.get("whisper_loaded") is True)
    except Exception as e:
        fail("健康检查异常", str(e))

    r = client.get("/")
    check("根路径返回服务信息", r.status_code == 200 and "Voice Chat Assistant" in r.json().get("service", ""))

    # ──────────────────────────────────────────────────────────
    section("2. 认证 — 注册")
    # ──────────────────────────────────────────────────────────
    # 先清理可能存在的测试账号（忽略错误）
    TEST_EMAIL = "pytest_user@voice-test.com"
    TEST_PASS = "PyTest1234"
    TEST_USER = "PyTestUser"

    r = client.post("/api/auth/register", json={
        "email": TEST_EMAIL, "password": TEST_PASS, "username": TEST_USER
    })
    if r.status_code in (200, 201):
        d = r.json()
        token = d.get("access_token")
        check("注册成功 (201)", r.status_code == 201)
        check("返回 access_token", bool(token))
        check("返回 user 对象", "user" in d)
        check("用户 email 正确", d["user"]["email"] == TEST_EMAIL)
        check("is_active = True", d["user"]["is_active"] is True)
    elif r.status_code == 400 and "已被注册" in r.text:
        # 账号已存在，用登录获取 token
        ok("注册（账号已存在，跳转登录）", "400 already registered")
    else:
        fail("注册返回意外状态", f"{r.status_code}: {r.text[:80]}")

    # 密码弱
    r = client.post("/api/auth/register", json={"email": "x@y.com", "password": "abc", "username": "x"})
    check("弱密码被拒绝 (422)", r.status_code == 422)

    # 无字母密码
    r = client.post("/api/auth/register", json={"email": "x@y.com", "password": "12345678", "username": "x"})
    check("纯数字密码被拒绝 (422)", r.status_code == 422)

    # 重复注册
    r = client.post("/api/auth/register", json={
        "email": TEST_EMAIL, "password": TEST_PASS, "username": TEST_USER
    })
    check("重复注册被拒绝 (400)", r.status_code == 400)

    # ──────────────────────────────────────────────────────────
    section("3. 认证 — 登录")
    # ──────────────────────────────────────────────────────────
    r = client.post("/api/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASS})
    check("登录成功 (200)", r.status_code == 200)
    if r.status_code == 200:
        d = r.json()
        token = d.get("access_token")
        check("返回 access_token", bool(token), token[:20] + "…" if token else "")
        check("token_type = bearer", d.get("token_type") == "bearer")

    r = client.post("/api/auth/login", json={"email": TEST_EMAIL, "password": "WrongPass9"})
    check("错误密码被拒绝 (401)", r.status_code == 401)

    r = client.post("/api/auth/login", json={"email": "notexist@x.com", "password": "Test1234"})
    check("不存在邮箱被拒绝 (401)", r.status_code == 401)

    # ──────────────────────────────────────────────────────────
    section("4. 认证 — 当前用户 & 鉴权")
    # ──────────────────────────────────────────────────────────
    if not token:
        fail("Token 为空，跳过认证测试")
    else:
        auth = {"Authorization": f"Bearer {token}"}

        r = client.get("/api/auth/me", headers=auth)
        check("GET /api/auth/me 返回 200", r.status_code == 200)
        if r.status_code == 200:
            d = r.json()
            check("email 正确", d.get("email") == TEST_EMAIL)
            check("username 正确", d.get("username") == TEST_USER)

        r = client.get("/api/auth/me")
        check("无 Token 访问返回 401", r.status_code == 401)

        r = client.get("/api/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
        check("无效 Token 返回 401", r.status_code == 401)

    # ──────────────────────────────────────────────────────────
    section("5. 对话管理")
    # ──────────────────────────────────────────────────────────
    if not token:
        fail("Token 为空，跳过对话测试")
    else:
        auth = {"Authorization": f"Bearer {token}"}

        # 创建对话
        r = client.post("/api/conversations", json={"title": "测试对话1"}, headers=auth)
        check("创建对话 (201)", r.status_code == 201)
        if r.status_code == 201:
            conv1 = r.json()
            conv_id = conv1["id"]
            check("对话有 id", bool(conv_id))
            check("对话标题正确", conv1["title"] == "测试对话1")
            check("voice_model_id 可为 null", "voice_model_id" in conv1)

        # 创建第二个对话
        r = client.post("/api/conversations", json={"title": "测试对话2"}, headers=auth)
        check("创建第二个对话 (201)", r.status_code == 201)
        conv2_id = r.json().get("id") if r.status_code == 201 else None

        # 列出对话
        r = client.get("/api/conversations", headers=auth)
        check("获取对话列表 (200)", r.status_code == 200)
        if r.status_code == 200:
            convs = r.json()
            check("对话列表有数据", len(convs) >= 2)
            check("对话有 message_count 字段", all("message_count" in c for c in convs))
            check("按 updated_at 倒序", convs[0]["id"] >= convs[-1]["id"])

        # 获取对话消息
        if conv_id:
            r = client.get(f"/api/conversations/{conv_id}/messages", headers=auth)
            check("获取消息列表 (200)", r.status_code == 200)
            check("新对话消息为空", r.json() == [])

        # 更新标题（后端接收 JSON body，不是 query param）
        # Update title (backend expects a JSON body, not a query parameter)
        if conv_id:
            r = client.patch(f"/api/conversations/{conv_id}/title",
                             headers=auth, json={"title": "已更新标题"})
            check("更新对话标题 (200)", r.status_code == 200)
            if r.status_code == 200:
                check("标题已更新", r.json().get("title") == "已更新标题")

        # 越权访问（用另一个用户测试 — 先注册另一个用户）
        r2 = client.post("/api/auth/register", json={
            "email": "other_pytest@voice-test.com", "password": "Other1234", "username": "Other"
        })
        if r2.status_code in (200, 201):
            other_token = r2.json().get("access_token")
        else:
            other_login = client.post("/api/auth/login", json={
                "email": "other_pytest@voice-test.com", "password": "Other1234"
            })
            other_token = other_login.json().get("access_token") if other_login.status_code == 200 else None

        if other_token and conv_id:
            other_auth = {"Authorization": f"Bearer {other_token}"}
            r = client.get(f"/api/conversations/{conv_id}/messages", headers=other_auth)
            check("跨用户访问对话被拒绝 (404)", r.status_code == 404)

        # 删除对话
        if conv2_id:
            r = client.delete(f"/api/conversations/{conv2_id}", headers=auth)
            check("删除对话 (200)", r.status_code == 200)
            # 验证已删除
            r = client.get(f"/api/conversations/{conv2_id}/messages", headers=auth)
            check("删除后访问返回 404", r.status_code == 404)

    # ──────────────────────────────────────────────────────────
    section("6. 音色管理")
    # ──────────────────────────────────────────────────────────
    if not token:
        fail("Token 为空，跳过音色测试")
    else:
        auth = {"Authorization": f"Bearer {token}"}

        # 列出音色
        r = client.get("/api/voices", headers=auth)
        check("获取音色列表 (200)", r.status_code == 200)
        voices = r.json() if r.status_code == 200 else []
        check("音色列表是数组", isinstance(voices, list))

        # 当前音色（可能为空）
        r = client.get("/api/voices/current/info", headers=auth)
        check("获取当前音色接口正常 (200 or 404)", r.status_code in (200, 404))

        # 上传非ZIP文件（应报错）
        import io
        fake_file = io.BytesIO(b"not a zip file content")
        r = client.post("/api/voices/import", headers=auth,
                        files={"file": ("test.zip", fake_file, "application/zip")})
        check("上传非法ZIP被拒绝 (4xx)", r.status_code >= 400,
              f"got {r.status_code}")

        # 不存在的音色
        r = client.get("/api/voices/999999", headers=auth)
        check("获取不存在音色返回 404", r.status_code == 404)

        r = client.delete("/api/voices/999999", headers=auth)
        check("删除不存在音色返回 404", r.status_code == 404)

        r = client.post("/api/voices/999999/select", headers=auth)
        check("选择不存在音色返回 404", r.status_code == 404)

    # ──────────────────────────────────────────────────────────
    section("7. 速率限制")
    # ──────────────────────────────────────────────────────────
    # 注册接口限 5/hour，登录限 10/min — 仅验证少量请求不触发限制
    r = client.post("/api/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASS})
    check("正常请求不触发限流", r.status_code == 200)

    # ──────────────────────────────────────────────────────────
    section("8. 边界条件")
    # ──────────────────────────────────────────────────────────
    if token:
        auth = {"Authorization": f"Bearer {token}"}

        # 对话标题过长
        r = client.post("/api/conversations",
                        json={"title": "A" * 300}, headers=auth)
        # FastAPI schema 会验证 max_length=255
        check("超长标题被截断或拒绝", r.status_code in (201, 422))
        if r.status_code == 201:
            # 如果允许创建，验证标题被截断
            created_title = r.json().get("title", "")
            check("超长标题被截断到255", len(created_title) <= 255)

        # 空 JSON body
        r = client.post("/api/auth/login", content=b"", headers={"Content-Type": "application/json"})
        check("空 body 返回 422", r.status_code == 422)

        # 错误 Content-Type
        r = client.post("/api/auth/login", content=b'{"email":"x","password":"y"}',
                        headers={"Content-Type": "text/plain"})
        check("错误 Content-Type 返回 422", r.status_code == 422)

    # ──────────────────────────────────────────────────────────
    section("汇总")
    # ──────────────────────────────────────────────────────────
    total = PASS_COUNT + FAIL_COUNT
    print(f"\n  通过: {PASS_COUNT}/{total}")
    print(f"  失败: {FAIL_COUNT}/{total}")
    if FAIL_COUNT == 0:
        print("\n  [PASS] All tests passed!")
    else:
        print("\n  [WARN] Some tests failed, check output above")

    client.close()
    return FAIL_COUNT


if __name__ == "__main__":
    fails = run_tests()
    sys.exit(1 if fails > 0 else 0)
