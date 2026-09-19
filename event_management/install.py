import os

import frappe


def after_install():
    """Run this app's setup patches on a fresh install.

    bench install_app marks every patch in patches.txt as already-applied for a
    brand-new site (set_all_patches_as_completed), so their execute() functions
    never actually run. Data patches (email templates, default settings, custom
    fields) would otherwise have to be run by hand with `bench execute`. Calling
    them here keeps a fresh install fully set up without any manual step.
    """
    sync_event_management_workspace()

    from event_management.patches import (
        add_event_trainer_linking_fields,
        add_trainer_management_fields,
        create_attendance_confirmation_email_template,
        create_default_settings,
        create_event_confirmation_role,
        create_registration_confirmation_email_template,
        create_welcome_email_template,
        drop_event_name_unique_index,
        increase_max_upload_file_size,
    )

    patch_modules = (
        create_attendance_confirmation_email_template,
        create_registration_confirmation_email_template,
        create_welcome_email_template,
        create_default_settings,
        create_event_confirmation_role,
        add_trainer_management_fields,
        add_event_trainer_linking_fields,
        increase_max_upload_file_size,
        drop_event_name_unique_index,
    )

    for patch_module in patch_modules:
        try:
            patch_module.execute()
        except Exception:
            frappe.log_error(
                title=f"event_management after_install: {patch_module.__name__} failed"
            )
            raise


def after_migrate():
    """Re-sync the "Event CB" workspace on every `bench migrate`.

    Same gap as after_install: the standard workspace sync that runs as part
    of migrate never picks this file up because of its folder layout, so an
    already-installed site would silently lose workspace updates otherwise.
    """
    sync_event_management_workspace()


def sync_event_management_workspace():
    """Import the "Event CB" workspace fixture explicitly.

    It lives at event_management/event_management/workspace/event_management.json
    instead of the workspace/<folder>/<folder>.json layout frappe.model.sync's
    get_doc_files() walks, so the standard doctype/workspace sync that runs
    during install and migrate silently skips it. Importing it here by exact
    path is a workaround, not a relocation of the file.
    """
    from frappe.modules.import_file import import_file_by_path

    workspace_path = os.path.join(
        frappe.get_app_path("event_management"),
        "event_management",
        "workspace",
        "event_management.json",
    )
    import_file_by_path(workspace_path, force=True)
