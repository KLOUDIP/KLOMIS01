/** @odoo-module */

import { messageActionsRegistry } from "@mail/core/common/message_actions";

// Re-register "delete" action with condition = false to hide it
messageActionsRegistry.add("delete", {
    ...messageActionsRegistry.get("delete"),
    condition: () => false,
}, { force: true });

// Re-register "edit" action with condition = false to hide it
messageActionsRegistry.add("edit", {
    ...messageActionsRegistry.get("edit"),
    condition: () => false,
}, { force: true });