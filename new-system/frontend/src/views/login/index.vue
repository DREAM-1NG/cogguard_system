<!--
  登录 / 注册页面

  居中表单，支持登录与注册模式切换。
  登录成功后保存 Token 并跳转首页；注册成功后自动切换到登录。
-->
<template>
  <div class="login-container">
    <div class="login-card">
      <div class="login-header">
        <h1>CogGuard</h1>
        <p>面向跨域认知操纵的智能联合防御系统</p>
      </div>

      <!-- 登录表单 -->
      <a-form
        v-if="!isRegister"
        :model="loginForm"
        :rules="loginRules"
        layout="vertical"
        @finish="handleLogin"
      >
        <a-form-item label="用户名" name="username">
          <a-input v-model:value="loginForm.username" placeholder="请输入用户名" size="large" />
        </a-form-item>
        <a-form-item label="密码" name="password">
          <a-input-password v-model:value="loginForm.password" placeholder="请输入密码" size="large" />
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
          <a-input v-model:value="registerForm.username" placeholder="3-64 个字符" size="large" />
        </a-form-item>
        <a-form-item label="邮箱" name="email">
          <a-input v-model:value="registerForm.email" placeholder="请输入邮箱" size="large" />
        </a-form-item>
        <a-form-item label="密码" name="password">
          <a-input-password v-model:value="registerForm.password" placeholder="至少 6 位" size="large" />
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
  try {
    await authStore.login(loginForm.username, loginForm.password)
    message.success('登录成功')
    router.push('/')
  } catch { /* handled */ } finally {
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
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
}

.login-card {
  width: 400px;
  padding: 48px 40px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
}

.login-header {
  text-align: center;
  margin-bottom: 32px;

  h1 {
    font-size: 28px;
    font-weight: 700;
    color: #1a1a2e;
    margin-bottom: 8px;
  }

  p {
    color: #666;
    font-size: 14px;
  }
}

.switch-mode {
  text-align: center;
  color: #666;
  font-size: 14px;
  margin-top: -8px;
}
</style>
