import { defineAsyncComponent, type App, type Component } from 'vue'

type AntDesignModule = Record<string, unknown>
type AntDesignLoader = () => Promise<AntDesignModule>
type ComponentSelector = (module: AntDesignModule) => Component

function selectDefault(module: AntDesignModule): Component {
  return selectPath('default')(module)
}

function selectPath(...path: string[]): ComponentSelector {
  return (module) => {
    let current: unknown = module
    for (const key of path) {
      current = (current as Record<string, unknown>)[key]
    }
    if (!current) throw new Error(`Ant Design component export is unavailable: ${path.join('.')}`)
    return current as Component
  }
}

function selectMember(...path: string[]): ComponentSelector {
  return selectPath('default', ...path)
}

function registerAsyncComponent(
  app: App,
  name: string,
  loader: AntDesignLoader,
  select: ComponentSelector = selectDefault,
): void {
  app.component(name, defineAsyncComponent({
    loader: () => loader().then(select),
    delay: 0,
    suspensible: false,
  }))
}

/**
 * Preserve the existing global a-* template vocabulary without importing every
 * Ant Design implementation into the initial application bundle.
 */
export function installAntDesignComponents(app: App): void {
  const avatar = () => import('ant-design-vue/es/avatar')
  const badge = () => import('ant-design-vue/es/badge')
  const card = () => import('ant-design-vue/es/card')
  const checkbox = () => import('ant-design-vue/es/checkbox')
  const col = () => import('ant-design-vue/es/col')
  const datePicker = () => import('ant-design-vue/es/date-picker')
  const descriptions = () => import('ant-design-vue/es/descriptions')
  const divider = () => import('ant-design-vue/es/divider')
  const drawer = () => import('ant-design-vue/es/drawer')
  const dropdown = () => import('ant-design-vue/es/dropdown')
  const form = () => import('ant-design-vue/es/form')
  const inputNumber = () => import('ant-design-vue/es/input-number')
  const layout = () => import('ant-design-vue/es/layout')
  const list = () => import('ant-design-vue/es/list')
  const menu = () => import('ant-design-vue/es/menu')
  const modal = () => import('ant-design-vue/es/modal')
  const popconfirm = () => import('ant-design-vue/es/popconfirm')
  const radio = () => import('ant-design-vue/es/radio')
  const row = () => import('ant-design-vue/es/row')
  const select = () => import('ant-design-vue/es/select')
  const slider = () => import('ant-design-vue/es/slider')
  const space = () => import('ant-design-vue/es/space')
  const switchComponent = () => import('ant-design-vue/es/switch')
  const table = () => import('ant-design-vue/es/table')
  const tabs = () => import('ant-design-vue/es/tabs')
  const timeline = () => import('ant-design-vue/es/timeline')
  const upload = () => import('ant-design-vue/es/upload')
  const semanticWorkspaceControls = () => import('./semanticWorkspaceControls')

  registerAsyncComponent(app, 'a-alert', semanticWorkspaceControls, selectPath('AAlert'))
  registerAsyncComponent(app, 'a-avatar', avatar)
  registerAsyncComponent(app, 'a-badge', badge)
  registerAsyncComponent(app, 'a-button', semanticWorkspaceControls, selectPath('AButton'))
  registerAsyncComponent(app, 'a-card', card)
  registerAsyncComponent(app, 'a-checkbox', checkbox)
  registerAsyncComponent(app, 'a-col', col)
  registerAsyncComponent(app, 'a-date-picker', datePicker)
  registerAsyncComponent(app, 'a-descriptions', descriptions)
  registerAsyncComponent(app, 'a-descriptions-item', descriptions, selectMember('Item'))
  registerAsyncComponent(app, 'a-divider', divider)
  registerAsyncComponent(app, 'a-drawer', drawer)
  registerAsyncComponent(app, 'a-dropdown', dropdown)
  registerAsyncComponent(app, 'a-empty', semanticWorkspaceControls, selectPath('AEmpty'))
  registerAsyncComponent(app, 'a-form', form)
  registerAsyncComponent(app, 'a-form-item', form, selectMember('Item'))
  registerAsyncComponent(app, 'a-input', semanticWorkspaceControls, selectPath('AInput'))
  registerAsyncComponent(app, 'a-input-number', inputNumber)
  registerAsyncComponent(app, 'a-input-password', semanticWorkspaceControls, selectPath('AInput', 'Password'))
  registerAsyncComponent(app, 'a-textarea', semanticWorkspaceControls, selectPath('AInput', 'TextArea'))
  registerAsyncComponent(app, 'a-layout', layout)
  registerAsyncComponent(app, 'a-layout-content', layout, selectMember('Content'))
  registerAsyncComponent(app, 'a-layout-header', layout, selectMember('Header'))
  registerAsyncComponent(app, 'a-layout-sider', layout, selectMember('Sider'))
  registerAsyncComponent(app, 'a-list', list)
  registerAsyncComponent(app, 'a-list-item', list, selectMember('Item'))
  registerAsyncComponent(app, 'a-list-item-meta', list, selectMember('Item', 'Meta'))
  registerAsyncComponent(app, 'a-menu', menu)
  registerAsyncComponent(app, 'a-menu-divider', menu, selectMember('Divider'))
  registerAsyncComponent(app, 'a-menu-item', menu, selectMember('Item'))
  registerAsyncComponent(app, 'a-modal', modal)
  registerAsyncComponent(app, 'a-pagination', semanticWorkspaceControls, selectPath('APagination'))
  registerAsyncComponent(app, 'a-popconfirm', popconfirm)
  registerAsyncComponent(app, 'a-popover', semanticWorkspaceControls, selectPath('APopover'))
  registerAsyncComponent(app, 'a-radio-button', radio, selectMember('Button'))
  registerAsyncComponent(app, 'a-radio-group', radio, selectMember('Group'))
  registerAsyncComponent(app, 'a-result', semanticWorkspaceControls, selectPath('AResult'))
  registerAsyncComponent(app, 'a-row', row)
  registerAsyncComponent(app, 'a-segmented', semanticWorkspaceControls, selectPath('ASegmented'))
  registerAsyncComponent(app, 'a-select', select)
  registerAsyncComponent(app, 'a-select-option', select, selectMember('Option'))
  registerAsyncComponent(app, 'a-skeleton', semanticWorkspaceControls, selectPath('ASkeleton'))
  registerAsyncComponent(app, 'a-slider', slider)
  registerAsyncComponent(app, 'a-space', space)
  registerAsyncComponent(app, 'a-spin', semanticWorkspaceControls, selectPath('ASpin'))
  registerAsyncComponent(app, 'a-switch', switchComponent)
  registerAsyncComponent(app, 'a-table', table)
  registerAsyncComponent(app, 'a-tab-pane', tabs, selectMember('TabPane'))
  registerAsyncComponent(app, 'a-tabs', tabs)
  registerAsyncComponent(app, 'a-tag', semanticWorkspaceControls, selectPath('ATag'))
  registerAsyncComponent(app, 'a-timeline', timeline)
  registerAsyncComponent(app, 'a-timeline-item', timeline, selectMember('Item'))
  registerAsyncComponent(app, 'a-tooltip', semanticWorkspaceControls, selectPath('ATooltip'))
  registerAsyncComponent(app, 'a-upload', upload)
}
