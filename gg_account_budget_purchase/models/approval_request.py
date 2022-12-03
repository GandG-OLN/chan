# -*- coding: utf-8 -*-

from odoo import fields, models


class ApprovalRequest(models.Model):
    _inherit = "approval.request"

    purchase_id = fields.Many2one('purchase.order', string="Purchase")
