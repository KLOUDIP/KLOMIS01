/* @odoo-module */

import { messageActionsRegistry } from "@mail/core/common/message_actions";
import { threadActionsRegistry } from "@mail/core/common/thread_actions";
import { Thread } from "@mail/core/common/thread_model";
import { ThreadService } from "@mail/core/common/thread_service";

import { patch } from "@web/core/utils/patch";

const deleteAction = messageActionsRegistry.get("delete");
patch(deleteAction, {
    condition(component) {
        return false;
    },
});

const editAction = messageActionsRegistry.get("edit");
patch(editAction, {
    condition(component) {
        return false;
    },
});
