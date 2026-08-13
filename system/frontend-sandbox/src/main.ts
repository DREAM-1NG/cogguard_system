/**
 * 应用入口
 *
 * 注册全局插件：Ant Design Vue、Pinia 状态管理、Vue Router。
 */
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import {
  Alert,
  Avatar,
  Badge,
  Button,
  Card,
  Checkbox,
  Col,
  Descriptions,
  Divider,
  Drawer,
  Dropdown,
  Empty,
  Form,
  Input,
  InputNumber,
  Layout,
  List,
  Menu,
  Modal,
  Popconfirm,
  Popover,
  Radio,
  Row,
  Segmented,
  Select,
  Slider,
  Space,
  Spin,
  Switch,
  Table,
  Tabs,
  Tag,
  Timeline,
  Tooltip,
  Upload,
} from 'ant-design-vue'
import 'ant-design-vue/dist/reset.css'

import App from './App.vue'
import router from './router'

const app = createApp(App)

app.use(createPinia())
app.use(router)
for (const component of [
  Alert,
  Avatar,
  Badge,
  Button,
  Card,
  Checkbox,
  Col,
  Descriptions,
  Divider,
  Drawer,
  Dropdown,
  Empty,
  Form,
  Input,
  InputNumber,
  Layout,
  List,
  Menu,
  Modal,
  Popconfirm,
  Popover,
  Radio,
  Row,
  Segmented,
  Select,
  Slider,
  Space,
  Spin,
  Switch,
  Table,
  Tabs,
  Tag,
  Timeline,
  Tooltip,
  Upload,
]) {
  app.use(component)
}

app.mount('#app')
