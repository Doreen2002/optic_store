frappe.provide("optic_store.scripts.extensions.scan_barcode")

frappe.listview_settings['Stock Entry'] = Object.assign(
  frappe.listview_settings['Stock Entry'] || {},
  optic_store.listview.stock_entry
);
