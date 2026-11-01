/**
 * Ant Design controls rendered together by the dense Semantic Evidence route.
 * Keeping them in one module avoids a request waterfall for the workspace
 * while leaving low-frequency controls behind the global async registry.
 */
import AAlert from 'ant-design-vue/es/alert'
import AButton from 'ant-design-vue/es/button'
import AEmpty from 'ant-design-vue/es/empty'
import AInput from 'ant-design-vue/es/input'
import APagination from 'ant-design-vue/es/pagination'
import APopover from 'ant-design-vue/es/popover'
import AResult from 'ant-design-vue/es/result'
import ASegmented from 'ant-design-vue/es/segmented'
import ASkeleton from 'ant-design-vue/es/skeleton'
import ASpin from 'ant-design-vue/es/spin'
import ATag from 'ant-design-vue/es/tag'
import ATooltip from 'ant-design-vue/es/tooltip'

export {
  AAlert,
  AButton,
  AEmpty,
  AInput,
  APagination,
  APopover,
  AResult,
  ASegmented,
  ASkeleton,
  ASpin,
  ATag,
  ATooltip,
}
