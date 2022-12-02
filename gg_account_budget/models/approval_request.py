# -*- coding: utf-8 -*-

from odoo import fields, models


class ApprovalRequest(models.Model):
    _inherit = "approval.request"

    purchase_id = fields.Many2one('purchase.order', string="Purchase", invisible=1)
    move_id = fields.Many2one('account.move', string="Invoice", invisible=1)
