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
          meta: { title: '传播监测' },
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
          meta: { title: '系统运维', roles: ['admin'] },
        },
        {
          path: 'risk',
          name: 'Risk',
          component: () => import('@/views/risk/index.vue'),
          meta: { title: '事件研判' },
        },
      ],
    },
  ],
})

router.beforeEach(async (to, _from, next) => {
  // 在 UI 沙盒环境中，强制放行所有路由，直接跳过登录验证
  if (to.path === '/login') {
    next('/')
  } else {
    next()
  }
})

export default router
