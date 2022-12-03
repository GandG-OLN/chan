# -*- conding: utf-8 -*-

from itertools import groupby

import logging
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError, UserError
from odoo.osv import expression
from odoo.tools.float_utils import float_is_zero

# from odoo.tools.misc import formatLang

_logger = logging.getLogger(__name__)

READONLY_STATES = {'purchase': [('readonly', True)], 'done': [('readonly', True)], 'cancel': [('readonly', True)]}


class Purchase(models.Model):
    _inherit = "purchase.order"

    def _check_exceeded_budget(self):
        approval_request_approved = self.approval_request_ids.filtered(
            lambda apr: apr.approval_type in 'purchase_overrun_budget' and apr.request_status in 'approved')

        if approval_request_approved:
            has_exceeded_budget = False
        else:
            has_exceeded_budget = self.has_exceeded_budget

        return has_exceeded_budget

    @api.depends('approval_request_ids')
    def _compute_approvals(self):
        for order in self:
            """
                Update exceeded statut
            """
            has_exceeded_budget = order._check_exceeded_budget()
            order.update({'has_exceeded_budget': has_exceeded_budget})

            order.approval_request_count = len(order.approval_request_ids)

    # Check available budget for current vendor
    def _get_available_budget_by_user(self):
        order_date = fields.Date.to_date(self.date_order) or fields.Date.today()
        user_id = self.user_id or self.env.user
        return expression.AND(
            [
                [('state', '=', 'validate')],
                [('date_from', '<=', order_date)],
                [('date_to', '>=', order_date)],
                [('user_allowed_ids', 'in', [user_id.id])],
            ])

    budget_id = fields.Many2one('gg.crossovered.budget', string='Budget',
                                domain=lambda self: self._get_available_budget_by_user(), required=True,
                                state=READONLY_STATES)
    has_exceeded_budget = fields.Boolean(default=False, store=True)
    approval_request_ids = fields.One2many('approval.request', 'purchase_id', string="Demande d'approbation",
                                           tracking=True)
    approval_request_count = fields.Integer(compute="_compute_approvals", string='Approbations', copy=False, default=0)

    @api.constrains('date_order', 'user_id')
    def _check_user_id_date_order(self):
        for order in self:
            order._checking_budget_with_date_and_user()

    @api.onchange('date_order', 'user_id')
    def _onchange_date_user(self):
        self._checking_budget_with_date_and_user()

    def _checking_budget_with_date_and_user(self):
        if self.budget_id:
            budget_id = self.budget_id.id
            order_date = fields.Date.to_date(self.date_order) or fields.Date.today()
            user_id = self.user_id or self.env.user
            available_budget = self.env['gg.crossovered.budget'].search(expression.AND([
                [('id', '=', budget_id)],
                [('state', '=', 'validate')],
                [('date_from', '<=', order_date)],
                [('date_to', '>=', order_date)],
                [('user_allowed_ids', 'in', [user_id.id])],
            ]))

            if not available_budget or (budget_id and budget_id not in available_budget.ids):
                raise ValidationError("Aucun budget défini pour la date (%s) ou utilisateur (%s)" % (
                    fields.Date.to_date(self.date_order), user_id.name))

    @api.onchange('budget_id', 'amount_total')
    def _onchange_budget(self):
        # Checking only of order have budget and line(s)
        if self.budget_id and self.order_line:
            msgs = ''
            # Get all account id
            account_ids = [p.property_account_expense_id or p.categ_id.property_account_expense_categ_id for p in
                           self.order_line.mapped('product_id')]
            for account in account_ids:
                budget_line = self.env['gg.crossovered.budget.lines'].search(expression.AND(
                    [[('budget_id', '=', self.budget_id.id)],
                     [('budget_post_id.account_ids', 'in', account.id)], ]), limit=1)
                if not budget_line:
                    msgs += "Aucun poste budgétaire associé à ce compte %s\n" % account.name
            if msgs:
                raise ValidationError(msgs)

            # Verify that the amount does not exceed committed amount
            for account in account_ids:
                account_amount = sum(self.order_line.filtered(lambda
                                                                  l: l.product_id.property_account_expense_id.id == account.id or l.product_id.categ_id.property_account_expense_categ_id.id).mapped(
                    'price_total'))
                budget_line = self.env['gg.crossovered.budget.lines'].search(expression.AND(
                    [[('budget_id', '=', self.budget_id.id)],
                     [('budget_post_id.account_ids', 'in', account.id)], ]), limit=1)

                if abs(budget_line.planned_amount) < abs(budget_line.committed_amount) + account_amount:
                    _logger.info('========= HAS EXCEEDED %s, BUDGET PRATICAL AMOUNT %s', True,
                                 abs(budget_line.practical_amount))
                    self.update({'has_exceeded_budget': True})
                else:
                    self.update({'has_exceeded_budget': False})

                _logger.info("======== COMPTE: %s, AMOUNT: %s", account.code, account_amount)

    def button_request_for_approval_budget(self):
        for order in self:
            approval_request = order.approval_request_ids.filtered(
                lambda apr: apr.approval_type in 'purchase_overrun_budget')
            if not approval_request:
                approval_category_id = self.env.ref(
                    'gg_account_budget_purchase.approval_category_data_purchase_approval_budget')
                approval = self.env['approval.request']

                # Create new approval overrun budget
                result = approval.create(
                    {'name': approval_category_id.sequence_id.next_by_id(), 'request_owner_id': self.env.uid,
                     'category_id': approval_category_id.id,
                     'approval_minimum': approval_category_id.approval_minimum, 'reference': order.name,
                     'purchase_id': order.id, 'partner_id': order.partner_id.id,
                     'reason': "Demande de dépassement budgétaire pour la demande d'achat %s" % order.name, })

                # add approvers for this SO
                if result:
                    for approver in order.budget_id.approver_ids:
                        self.env['approval.approver'].create(
                            {'user_id': approver.user_id.id, 'request_id': result.id, 'status': 'new'})
                    return {'type': 'ir.actions.act_window', 'res_model': 'approval.request', 'view_mode': 'form',
                            'res_id': result.id, 'views': [(False, 'form')], }
                return result
            else:
                raise UserError(
                    "Il existe une demande d'approbation avec cette référence : %s" % order.approval_request_ids[
                        0].name)

    def action_view_approval(self):
        """
        This function returns an action that display existing approval of
        given purchase order id. When only one found, show the approval request
        immediately.
        """
        result = self.env['ir.actions.act_window']._for_xml_id('approvals.approval_request_action')
        # choose the view_mode accordingly
        if len(self.approval_request_ids) > 1:
            result['domain'] = [('id', 'in', self.approval_request_ids.ids)]
        elif len(self.approval_request_ids) == 1:
            res = self.env.ref('approvals.approval_request_view_form', False)
            form_view = [(res and res.id or False, 'form')]
            if 'views' in result:
                result['views'] = form_view + [(state, view) for state, view in result['views'] if view != 'form']
            else:
                result['views'] = form_view
            result['res_id'] = self.approval_request_ids.id
        else:
            result = {'type': 'ir.actions.act_window_close'}

        return result

    # Override action create invoice
    def action_create_invoice(self):
        """Create the invoice associated to the PO.
        """
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')

        # 1) Prepare invoice vals and clean-up the section lines
        invoice_vals_list = []
        for order in self:
            if order.invoice_status != 'to invoice':
                continue

            order = order.with_company(order.company_id)
            pending_section = None
            # Invoice values.
            invoice_vals = order._prepare_invoice()

            # Set budget define on purchase
            invoice_vals['budget_id'] = order.budget_id
            _logger.info("========= INVOICE VALS: %s", invoice_vals)

            # Invoice line values (keep only necessary sections).
            for line in order.order_line:
                if line.display_type == 'line_section':
                    pending_section = line
                    continue
                if not float_is_zero(line.qty_to_invoice, precision_digits=precision):
                    if pending_section:
                        invoice_vals['invoice_line_ids'].append((0, 0, pending_section._prepare_account_move_line()))
                        pending_section = None
                    invoice_vals['invoice_line_ids'].append((0, 0, line._prepare_account_move_line()))
            invoice_vals_list.append(invoice_vals)

        if not invoice_vals_list:
            raise UserError(
                _('There is no invoiceable line. If a product has a control policy based on received quantity, please make sure that a quantity has been received.'))

        # 2) group by (company_id, partner_id, currency_id) for batch creation
        new_invoice_vals_list = []
        for grouping_keys, invoices in groupby(invoice_vals_list, key=lambda x: (
                x.get('company_id'), x.get('partner_id'), x.get('currency_id'))):
            origins = set()
            payment_refs = set()
            refs = set()
            ref_invoice_vals = None
            for invoice_vals in invoices:
                if not ref_invoice_vals:
                    ref_invoice_vals = invoice_vals
                else:
                    ref_invoice_vals['invoice_line_ids'] += invoice_vals['invoice_line_ids']
                origins.add(invoice_vals['invoice_origin'])
                payment_refs.add(invoice_vals['payment_reference'])
                refs.add(invoice_vals['ref'])
            ref_invoice_vals.update({
                'ref': ', '.join(refs)[:2000],
                'invoice_origin': ', '.join(origins),
                'payment_reference': len(payment_refs) == 1 and payment_refs.pop() or False,
            })
            new_invoice_vals_list.append(ref_invoice_vals)
        invoice_vals_list = new_invoice_vals_list

        # 3) Create invoices.
        moves = self.env['account.move']
        AccountMove = self.env['account.move'].with_context(default_move_type='in_invoice')
        for vals in invoice_vals_list:
            moves |= AccountMove.with_company(vals['company_id']).create(vals)

        # 4) Some moves might actually be refunds: convert them if the total amount is negative
        # We do this after the moves have been created since we need taxes, etc. to know if the total
        # is actually negative or not
        moves.filtered(
            lambda m: m.currency_id.round(m.amount_total) < 0).action_switch_invoice_into_refund_credit_note()

        return self.action_view_invoice(moves)
