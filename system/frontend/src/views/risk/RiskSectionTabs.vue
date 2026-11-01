<template>
  <nav class="risk-section-tabs" aria-label="事件研判页面">
    <router-link
      v-for="section in sections"
      :key="section.path"
      class="risk-section-tab"
      :class="{ 'is-active': isActive(section.path) }"
      :to="{ path: section.path, query: scopeQuery }"
      :aria-current="isActive(section.path) ? 'page' : undefined"
    >
      {{ section.label }}
    </router-link>
  </nav>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { LocationQueryRaw } from 'vue-router'
import { useRoute } from 'vue-router'

const props = defineProps<{
  eventId?: string
  caseId?: string
}>()

const route = useRoute()
const sections = [
  { path: '/risk', label: '研判概览' },
  { path: '/risk/semantic-evidence', label: '语义证据' },
]

const scopeQuery = computed<LocationQueryRaw>(() => {
  const query: LocationQueryRaw = {}
  const eventId = props.eventId?.trim()
  const caseId = props.caseId?.trim()
  if (eventId) query.event_id = eventId
  if (caseId) query.case_id = caseId
  return query
})

function isActive(path: string): boolean {
  return route.path === path
}
</script>

<style scoped>
.risk-section-tabs {
  display: flex;
  gap: 2px;
  margin: 0 0 16px;
  max-width: 100%;
  overflow-x: auto;
  border-bottom: 1px solid #d9e2ec;
}

.risk-section-tab {
  flex: 0 0 auto;
  padding: 9px 12px 8px;
  border-bottom: 2px solid transparent;
  color: #52667c;
  font-size: 13px;
  line-height: 1.45;
  text-decoration: none;
}

.risk-section-tab:hover {
  color: #1d67a0;
  background: #f5faff;
}

.risk-section-tab.is-active {
  border-bottom-color: #1d67a0;
  color: #124a73;
  font-weight: 650;
}

.risk-section-tab:focus-visible {
  outline: 3px solid #91caff;
  outline-offset: -2px;
}

@media (max-width: 720px) {
  .risk-section-tab {
    padding-right: 10px;
    padding-left: 10px;
  }
}
</style>
