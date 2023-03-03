import frappe
import requests
import json
from frappe import *
from gst_india.utils import (success_response, error_response, 
                             response_error_handling, response_logger, 
                             get_dict,get_url,set_headers,process_request)


@frappe.whitelist()
def create_gst_invoice(**kwargs):
    try:
        invoice = kwargs.get('invoice')
        type = kwargs.get('type')
        if  type == "SALE":
            doctype = "Sales Invoice"
        else:
            doctype = "Purchase Invoice"
        invoice = frappe.get_doc(doctype,kwargs.get('invoice'))
        item_list = []
        gst_round_off = frappe.get_value('GST Settings','round_off_gst_values')
        gst_settings_accounts = frappe.get_all("GST Account",
                filters={'company':invoice.company},
                fields=["cgst_account", "sgst_account", "igst_account", "cess_account"])
        for row in invoice.items:
            item_list.append(get_dict('Item',row.item_code))
        data = {
            'invoice': invoice.as_dict(),
            'type': type,
            'item_list': item_list,
            'gst_accounts':gst_settings_accounts,
            'gst_round_off': gst_round_off
        }
        if type == 'SALE':
            data['company_address'] = get_dict('Address',invoice.company_address)
            data['customer'] = get_dict('Customer',invoice.customer)
            data['customer_address'] = get_dict('Address',invoice.customer_address)
            data['shipping_address'] = get_dict('Address',invoice.shipping_address_name)
        else:
            data['company_address'] = get_dict('Address',invoice.supplier_address)
            data['customer_address'] = get_dict('Address',invoice.billing_address)
            data['shipping_address'] = get_dict('Address',invoice.shipping_address)
        if invoice.is_return:
            data['original_invoice'] = get_dict(doctype,invoice.return_against)
            # return gst_cdn_request(data,kwargs.get('invoice'),type)
        # if invoice.is_debit_note:
        #     data['original_invoice'] = get_dict('Sales Invoice',invoice.return_against)
        #     return gst_cdn_request(data,kwargs.get('invoice'),type)
        return gst_invoice_request(data,kwargs.get('invoice'),type)
    except Exception as e:
        frappe.logger('cleartax').exception(e)
        return error_response(e)


def gst_invoice_request(data,id,type):
    try:
        url = get_url()
        url+= "gst."
        headers = set_headers()
        if type == 'SALE':
            url+= 'gst_sales'
            gstin = data.get('company_address').get('gstin')
        else:
            url+= 'gst_purchase'
            gstin = data.get('customer_address').get('gstin')
        headers['gstin'] = gstin
        data = json.dumps(data, indent=4, sort_keys=False, default=str)
        response = requests.request("POST", url, headers=headers, data= data) 
        api = "GENERATE GST SINV" if type == 'SALE' else "GENERATE GST PINV"
        doctype = "Sales Invoice" if type == 'SALE' else "Purchase Invoice"
        response = process_request(response,api,doctype,id)
        if type == 'SALE':
            frappe.db.set_value('Sales Invoice',id,'gst_invoice',1)
        else:
            frappe.db.set_value('Purchase Invoice',id,'gst_invoice',1)
        frappe.db.commit()
        return success_response()
    except Exception as e:
        frappe.logger('cleartax').exception(e)
        return error_response(e)


def gst_cdn_request(data,id,type):
    try:
        url = get_url()
        url+= "gst.create_gst_invoice"
        headers = set_headers()
        if type == 'SALE':
            gstin = data.get('company_address').get('gstin')
        else:
            gstin = data.get('customer_address').get('gstin')
        data = json.dumps(data, indent=4, sort_keys=False, default=str)
        response = requests.request("PUT", url, headers=headers, data= data)
        api = "GENERATE GST CDN"
        doctype = "Sales Invoice" if type == 'SALE' else "Purchase Invoice"
        response = process_request(response,api,doctype,id)
        if type == 'SALE':
            frappe.db.set_value('Sales Invoice',id,'cdn',1)
        else:
            frappe.db.set_value('Purchase Invoice',id,'cdn',1)
        frappe.db.commit()
        return success_response(response['response'])
    except Exception as e:
        frappe.logger('cleartax').exception(e)
        return error_response(e)

@frappe.whitelist()
def bulk_purchase_gst(**kwargs):
    try:
        data = json.loads(kwargs.get('data'))
        for i in data:
            frappe.enqueue("gst_india.API.gst.create_gst_invoice",**{'invoice':i,'type':'PURCHASE'})
    except Exception as e:
        frappe.logger('sfa_online').exception(e)