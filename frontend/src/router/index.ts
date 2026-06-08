import { createRouter, createWebHistory } from "vue-router";

import { getWhoAmI } from "../services/api";
import MasterGuideView from "../views/MasterGuideView.vue";
import MasterReportView from "../views/MasterReportView.vue";
import PlannedSourcesView from "../views/PlannedSourcesView.vue";
import AdminView from "../views/AdminView.vue";
import ReferenceView from "../views/ReferenceView.vue";
import RawDataView from "../views/RawDataView.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", name: "references", component: ReferenceView },
    { path: "/raw", name: "raw", component: RawDataView },
    { path: "/master-report", name: "master-report", component: MasterReportView },
    { path: "/master-guide", name: "master-guide", component: MasterGuideView },
    {
      path: "/planned-sources",
      name: "planned-sources",
      component: PlannedSourcesView,
      meta: { requiresAdmin: true }
    },
    { path: "/admin", name: "admin", component: AdminView, meta: { requiresAdmin: true } }
  ]
});

router.beforeEach(async (to) => {
  if (!to.meta.requiresAdmin) {
    return true;
  }
  try {
    const user = await getWhoAmI();
    if (user.can_view_audit) {
      return true;
    }
  } catch {
    // deny access when identity is unavailable
  }
  return { path: "/" };
});

export default router;
