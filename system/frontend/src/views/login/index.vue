<!--
  登录 / 注册页面

  居中表单，支持登录与注册模式切换。
  登录成功后保存 Token 并跳转首页；注册成功后自动切换到登录。
-->
<template>
  <div class="login-container">
    <div class="login-shell">
      <section class="brand-panel">
        <div class="brand-content">
          <div class="brand-wordmark">CogGuard</div>
          <h1>面向跨域认知操纵的智能联合防御系统</h1>
        </div>
      </section>

      <div class="login-card">
        <div class="login-header">
          <h2>{{ isRegister ? 'Create CogGuard Account' : 'Welcome to CogGuard' }}</h2>
          <p>{{ isRegister ? '填写以下信息完成注册' : '请输入账户信息进行登录' }}</p>
        </div>

        <!-- 登录表单 -->
        <a-form
          v-if="!isRegister"
          :model="loginForm"
          :rules="loginRules"
          layout="vertical"
          @finish="handleLogin"
        >
          <a-alert
            v-if="loginError"
            class="login-error"
            type="error"
            show-icon
            :message="loginError"
          />
          <a-form-item label="用户名" name="username">
            <a-input
              v-model:value="loginForm.username"
              name="username"
              autocomplete="username"
              :spellcheck="false"
              placeholder="请输入用户名…"
              size="large"
              @change="loginError = ''"
            />
          </a-form-item>
          <a-form-item label="密码" name="password">
            <a-input-password
              v-model:value="loginForm.password"
              name="password"
              autocomplete="current-password"
              placeholder="请输入密码…"
              size="large"
              @change="loginError = ''"
            />
          </a-form-item>
          <a-form-item>
            <a-button type="primary" html-type="submit" size="large" :loading="loading" block>
              登 录
            </a-button>
          </a-form-item>
          <div class="switch-mode">
            还没有账号？<a-button type="link" @click="isRegister = true">立即注册</a-button>
          </div>
        </a-form>

        <!-- 注册表单 -->
        <a-form
          v-else
          :model="registerForm"
          :rules="registerRules"
          layout="vertical"
          @finish="handleRegister"
        >
          <a-form-item label="用户名" name="username">
            <a-input
              v-model:value="registerForm.username"
              name="new-username"
              autocomplete="username"
              :spellcheck="false"
              placeholder="3-64 个字符…"
              size="large"
            />
          </a-form-item>
          <a-form-item label="邮箱" name="email">
            <a-input
              v-model:value="registerForm.email"
              name="email"
              autocomplete="email"
              :spellcheck="false"
              placeholder="请输入邮箱…"
              size="large"
            />
          </a-form-item>
          <a-form-item label="密码" name="password">
            <a-input-password
              v-model:value="registerForm.password"
              name="new-password"
              autocomplete="new-password"
              placeholder="至少 6 位…"
              size="large"
            />
          </a-form-item>
          <a-form-item>
            <a-button type="primary" html-type="submit" size="large" :loading="loading" block>
              注 册
            </a-button>
          </a-form-item>
          <div class="switch-mode">
            已有账号？<a-button type="link" @click="isRegister = false">返回登录</a-button>
          </div>
        </a-form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { useAuthStore } from '@/stores/auth'
import { register } from '@/api/auth'

const router = useRouter()
const authStore = useAuthStore()

const loading = ref(false)
const isRegister = ref(false)
const loginError = ref('')

const loginForm = reactive({ username: '', password: '' })
const registerForm = reactive({ username: '', email: '', password: '' })

const loginRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

const registerRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 64, message: '用户名 3-64 个字符', trigger: 'blur' },
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email' as const, message: '邮箱格式不正确', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 位', trigger: 'blur' },
  ],
}

async function handleLogin() {
  loading.value = true
  loginError.value = ''
  try {
    await authStore.login(loginForm.username, loginForm.password)
    message.success('登录成功')
    router.push('/')
  } catch (error: any) {
    const status = error?.response?.status
    const serverMessage = error?.response?.data?.msg || error?.message || ''
    if (status === 401 || serverMessage.includes('Invalid username or password')) {
      loginError.value = '用户名或密码错误，请重新输入'
    } else if (status >= 500) {
      loginError.value = '认证服务暂不可用，请稍后重试'
    } else {
      loginError.value = serverMessage || '登录失败，请稍后重试'
    }
    message.error(loginError.value)
  } finally {
    loading.value = false
  }
}

async function handleRegister() {
  loading.value = true
  try {
    await register(registerForm)
    message.success('注册成功，请登录')
    isRegister.value = false
    loginForm.username = registerForm.username
    loginForm.password = ''
  } catch { /* handled */ } finally {
    loading.value = false
  }
}
</script>

<style scoped lang="less">
.login-container {
  --ink: #071224;
  --muted: #6b7385;
  --panel-blue: #102647;
  --panel-cyan: #1ac8d8;
  --panel-orange: #ff8a3d;

  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 32px;
  overflow: hidden;
  background:
    radial-gradient(circle at 12% 18%, rgba(26, 200, 216, 0.22), transparent 32%),
    radial-gradient(circle at 88% 86%, rgba(255, 138, 61, 0.16), transparent 30%),
    linear-gradient(135deg, #071224 0%, #102647 52%, #14345f 100%);
  font-family: "HarmonyOS Sans SC", "Source Han Sans SC", "Microsoft YaHei", sans-serif;
}

.login-shell {
  position: relative;
  display: grid;
  grid-template-columns: minmax(360px, 0.92fr) minmax(420px, 1fr);
  width: min(1120px, 100%);
  min-height: 650px;
  border: 1px solid rgba(255, 255, 255, 0.22);
  border-radius: 28px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 34px 90px rgba(3, 10, 25, 0.42);
}

.brand-panel {
  position: relative;
  display: flex;
  align-items: center;
  min-height: 650px;
  padding: 64px 56px;
  color: #fff;
  isolation: isolate;
  background:
    linear-gradient(135deg, rgba(10, 28, 58, 0.94), rgba(18, 74, 111, 0.9)),
    repeating-radial-gradient(circle at 35% 30%, rgba(255, 255, 255, 0.1) 0 1px, transparent 1px 18px);
}

.brand-panel::before,
.brand-panel::after {
  position: absolute;
  inset: auto;
  z-index: -1;
  content: "";
  border-radius: 999px;
  filter: blur(1px);
}

.brand-panel::before {
  top: 72px;
  right: -120px;
  width: 280px;
  height: 280px;
  background: radial-gradient(circle, rgba(26, 200, 216, 0.44), transparent 65%);
}

.brand-panel::after {
  bottom: -86px;
  left: -72px;
  width: 300px;
  height: 300px;
  background: radial-gradient(circle, rgba(255, 138, 61, 0.35), transparent 68%);
}

.brand-content {
  position: relative;
  z-index: 1;
  max-width: 390px;
}

.brand-wordmark {
  margin-bottom: 42px;
  font-size: 46px;
  font-weight: 800;
  line-height: 1;
  letter-spacing: 0.04em;
  text-shadow: 0 12px 36px rgba(0, 0, 0, 0.28);
}

.brand-content h1 {
  margin: 0;
  font-size: 30px;
  font-weight: 700;
  line-height: 1.55;
  letter-spacing: 0.02em;
}

.brand-content h1::after {
  display: block;
  width: 88px;
  height: 4px;
  margin-top: 30px;
  content: "";
  border-radius: 99px;
  background: linear-gradient(90deg, var(--panel-cyan), var(--panel-orange));
}

.login-card {
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 64px 76px;
  background:
    radial-gradient(circle at 86% 10%, rgba(26, 200, 216, 0.1), transparent 28%),
    linear-gradient(180deg, #f8fbff 0%, #ffffff 100%);
}

.login-header {
  margin-bottom: 34px;

  h2 {
    margin: 0 0 10px;
    font-size: 30px;
    font-weight: 800;
    color: var(--ink);
    letter-spacing: 0.01em;
  }

  p {
    margin: 0;
    color: var(--muted);
    font-size: 15px;
  }
}

:deep(.ant-form-item-label > label) {
  color: #27354c;
  font-weight: 650;
}

:deep(.ant-input),
:deep(.ant-input-affix-wrapper) {
  min-height: 48px;
  border-color: #d7deea;
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 8px 24px rgba(20, 52, 95, 0.06);
}

:deep(.ant-input:focus),
:deep(.ant-input-focused),
:deep(.ant-input-affix-wrapper-focused) {
  border-color: var(--panel-cyan);
  box-shadow: 0 0 0 3px rgba(26, 200, 216, 0.16);
}

:deep(.ant-btn-primary) {
  height: 50px;
  border: none;
  border-radius: 13px;
  background: linear-gradient(90deg, #1177ff, #1ac8d8);
  box-shadow: 0 14px 28px rgba(17, 119, 255, 0.28);
  font-size: 17px;
  font-weight: 700;
}

:deep(.ant-btn-primary:hover) {
  background: linear-gradient(90deg, #0e68df, #15b6c5);
}

:deep(.ant-btn-link) {
  color: #1177ff;
  font-weight: 700;
}

.login-error {
  margin-bottom: 18px;
  border-color: rgba(255, 138, 61, 0.32);
  border-radius: 14px;
  background: rgba(255, 244, 238, 0.95);
}

.switch-mode {
  margin-top: -4px;
  text-align: center;
  color: var(--muted);
  font-size: 14px;
}

@media (max-width: 900px) {
  .login-container {
    padding: 20px;
  }

  .login-shell {
    grid-template-columns: 1fr;
    min-height: auto;
  }

  .brand-panel {
    min-height: 250px;
    padding: 44px 34px;
  }

  .brand-wordmark {
    margin-bottom: 22px;
    font-size: 36px;
  }

  .brand-content h1 {
    font-size: 22px;
  }

  .login-card {
    padding: 40px 28px 44px;
  }

  .login-header {
    margin-bottom: 8px;

    h2 {
      font-size: 25px;
    }
  }
}
</style>
