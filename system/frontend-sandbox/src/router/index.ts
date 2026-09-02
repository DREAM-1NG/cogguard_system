import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('@/views/login/index.vue'),
      meta: { requiresAuth: false },
    },
    {
      path: '/preview',
      redirect: '/?preview=1',
      meta: { requiresAuth: false },
    },
    {
      path: '/',
      redirect: '/dashboard',
      meta: { requiresAuth: true },
    },
    {
      path: '/',
      component: () => import('@/components/layout/BasicLayout.vue'),
      meta: { requiresAuth: true },
      children: [
        {
          path: 'dashboard',
          name: 'Dashboard',
          component: () => import('@/views/dashboard/index.vue'),
          meta: { title: '数据大屏' },
        },
        {
          path: 'crawl',
          name: 'Crawl',
          component: () => import('@/views/crawl/index.vue'),
          meta: { title: '数据采集' },
        },
        {
          path: 'coordination',
          name: 'Coordination',
          component: () => import('@/views/coordination/index.vue'),
          meta: { title: '协同发现' },
        },
        {
          path: 'propagation',
          name: 'Propagation',
          component: () => import('@/views/propagation/index.vue'),
          meta: { title: '传播分析' },
        },
        {
          path: 'accounts',
          name: 'Accounts',
          component: () => import('@/views/accounts/index.vue'),
          meta: { title: '账号画像' },
        },
        {
          path: 'system',
          name: 'SystemManagement',
          component: () => import('@/views/system/index.vue'),
          meta: { title: '系统管理', roles: ['admin'] },
        },
        {
          path: 'risk',
          name: 'Risk',
          component: () => import('@/views/risk/index.vue'),
          meta: { title: '风险研判' },
        },
      ],
    },
  ],
})

router.beforeEach(async (to, _from, next) => {
  const wantsPreview = to.query.preview === '1' || to.path === '/preview'
  if (wantsPreview) {
    const { useAuthStore } = await import('@/stores/auth')
    const authStore = useAuthStore()
    authStore.enablePreview()
    if (to.path === '/preview') {
      next('/')
    } else {
      next({ path: to.path, query: {}, replace: true })
    }
    return
  }

  const token = localStorage.getItem('access_token')
  if (to.meta.requiresAuth !== false && !token) {
    next('/login')
  } else if (to.path === '/login' && token) {
    next('/')
  } else {
    const requiredRoles = to.meta.roles as string[] | undefined
    if (requiredRoles?.length) {
      const { useAuthStore } = await import('@/stores/auth')
      const authStore = useAuthStore()
      if (!authStore.userInfo) {
        try {
          await authStore.fetchProfile()
        } catch {
          authStore.logout()
          return
        }
      }
      const currentRole = authStore.userInfo?.role || ''
      if (!requiredRoles.includes(currentRole)) {
        next('/')
        return
      }
    }
    next()
  }
})

export default router
