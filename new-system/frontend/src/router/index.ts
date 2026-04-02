/**
 * 路由配置
 *
 * 定义页面路由和导航守卫：
 * - 未登录用户访问受保护页面时自动跳转 /login
 * - 已登录用户访问 /login 时自动跳转首页
 */
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
      component: () => import('@/components/layout/BasicLayout.vue'),
      meta: { requiresAuth: true },
      children: [
        {
          path: '',
          name: 'Dashboard',
          component: () => import('@/views/dashboard/index.vue'),
          meta: { title: '监测看板' },
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
          meta: { title: '协同检测' },
        },
        {
          path: 'propagation',
          name: 'Propagation',
          component: () => import('@/views/propagation/index.vue'),
          meta: { title: '传播归因' },
        },
        {
          path: 'accounts',
          name: 'Accounts',
          component: () => import('@/views/accounts/index.vue'),
          meta: { title: '账户监测' },
        },
      ],
    },
  ],
})

/** 全局导航守卫 */
router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('access_token')
  if (to.meta.requiresAuth !== false && !token) {
    next('/login')
  } else if (to.path === '/login' && token) {
    next('/')
  } else {
    next()
  }
})

export default router
