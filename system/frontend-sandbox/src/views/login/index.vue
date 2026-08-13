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
          <h2>{{ isRegister ? '注册账户' : '登录系统' }}</h2>
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
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 32px;
  overflow: hidden;
  background: #FAF9F6;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}

.login-shell {
  position: relative;
  display: grid;
  grid-template-columns: minmax(360px, 0.92fr) minmax(420px, 1fr);
  width: min(1040px, 100%);
  min-height: 580px;
  border: 1px solid #E4E4E7;
  border-radius: 8px;
  overflow: hidden;
  background: #FFFFFF;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
}

.brand-panel {
  position: relative;
  display: flex;
  align-items: center;
  min-height: 580px;
  padding: 64px 56px;
  color: #FFFFFF;
  background: #18181B;
  border-right: 1px solid #27272A;
}

.brand-content {
  position: relative;
  z-index: 1;
  max-width: 390px;
}

.brand-wordmark {
  margin-bottom: 32px;
  font-size: 40px;
  font-weight: 800;
  line-height: 1;
  letter-spacing: 0.02em;
}

.brand-content h1 {
  margin: 0;
  font-size: 26px;
  font-weight: 600;
  line-height: 1.5;
  letter-spacing: 0.01em;
  color: #FFFFFF;
}

.brand-content h1::after {
  display: block;
  width: 60px;
  height: 3px;
  margin-top: 24px;
  content: "";
  border-radius: 99px;
  background: #FFFFFF;
}

.login-card {
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 56px 64px;
  background: #FFFFFF;
}

.login-header {
  margin-bottom: 32px;

  h2 {
    margin: 0 0 8px;
    font-size: 26px;
    font-weight: 700;
    color: #18181B;
    letter-spacing: 0.01em;
  }

  p {
    margin: 0;
    color: #71717A;
    font-size: 14px;
  }
}

:deep(.ant-form-item-label > label) {
  color: #18181B;
  font-weight: 600;
}

:deep(.ant-input),
:deep(.ant-input-affix-wrapper) {
  min-height: 44px;
  border-color: #E4E4E7;
  border-radius: 6px;
  background: #FFFFFF;
  box-shadow: none;
}

:deep(.ant-input:focus),
:deep(.ant-input-focused),
:deep(.ant-input-affix-wrapper-focused) {
  border-color: #18181B;
  box-shadow: 0 0 0 2px rgba(24, 24, 27, 0.1);
}

:deep(.ant-btn-primary) {
  height: 44px;
  border: none;
  border-radius: 6px;
  background: #18181B;
  color: #FFFFFF;
  box-shadow: none;
  font-size: 15px;
  font-weight: 600;
}

:deep(.ant-btn-primary:hover) {
  background: #27272A;
}

:deep(.ant-btn-link) {
  color: #2563EB;
  font-weight: 600;
}

.login-error {
  margin-bottom: 18px;
  border-color: #FECACA;
  border-radius: 6px;
  background: #FEF2F2;
}

.switch-mode {
  margin-top: 4px;
  text-align: center;
  color: #71717A;
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
    min-height: 220px;
    padding: 36px 28px;
  }

  .brand-wordmark {
    margin-bottom: 18px;
    font-size: 32px;
  }

  .brand-content h1 {
    font-size: 20px;
  }

  .login-card {
    padding: 36px 24px;
  }

  .login-header {
    margin-bottom: 16px;

    h2 {
      font-size: 22px;
    }
  }
}
</style>
