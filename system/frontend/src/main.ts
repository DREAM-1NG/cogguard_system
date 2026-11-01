/**
 * 应用入口
 *
 * 注册全局插件：Ant Design Vue、Pinia 状态管理、Vue Router。
 */
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import 'ant-design-vue/dist/reset.css'

import App from './App.vue'
import router from './router'
import { installAntDesignComponents } from './ui/antDesignComponents'

const app = createApp(App)

app.use(createPinia())
installAntDesignComponents(app)
app.use(router)

app.mount('#app')
